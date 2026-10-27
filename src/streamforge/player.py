# src/streamforge/player.py
"""
Stream playback via mpv or vlc.

The resolver returns URLs in the form 'url|Header1=val1&Header2=val2'.
This module splits that, translates the headers to player-specific flags,
and launches the player as a subprocess.

Player lookup order:
  1. tools/mpv/mpv.exe     (installed by player_setup)
  2. tools/vlc/vlc.exe
  3. mpv on PATH
  4. vlc on PATH
"""

import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

from .ui import console, info, ok, warn, err


# ===================================================================
# Paths
# ===================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Portable install locations (written by player_setup)
PORTABLE_MPV = PROJECT_ROOT / "tools" / "mpv" / "mpv.exe"
PORTABLE_VLC = PROJECT_ROOT / "tools" / "vlc" / "vlc.exe"

# Common system install locations as last-resort fallbacks on Windows
_SYSTEM_MPV_CANDIDATES = (
    Path(r"C:\Program Files\mpv\mpv.exe"),
    Path(r"C:\Program Files (x86)\mpv\mpv.exe"),
)
_SYSTEM_VLC_CANDIDATES = (
    Path(r"C:\Program Files\VideoLAN\VLC\vlc.exe"),
    Path(r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"),
)


# ===================================================================
# Player discovery
# ===================================================================

def _find_mpv() -> str | None:
    """Return the path to a working mpv executable, or None."""
    # 1. Portable
    if PORTABLE_MPV.exists():
        return str(PORTABLE_MPV)
    # 2. PATH
    path = shutil.which("mpv")
    if path:
        return path
    # 3. Common system installs
    for p in _SYSTEM_MPV_CANDIDATES:
        if p.exists():
            return str(p)
    return None


def _find_vlc() -> str | None:
    """Return the path to a working vlc executable, or None."""
    if PORTABLE_VLC.exists():
        return str(PORTABLE_VLC)
    path = shutil.which("vlc")
    if path:
        return path
    for p in _SYSTEM_VLC_CANDIDATES:
        if p.exists():
            return str(p)
    return None


def detect_players() -> dict:
    """
    Return a dict {name: executable_path} for all available players.
    Checks portable installs first, then PATH, then common system paths.
    """
    found = {}
    mpv = _find_mpv()
    if mpv:
        found["mpv"] = mpv
    vlc = _find_vlc()
    if vlc:
        found["vlc"] = vlc
    return found


_cached_player: tuple[str, str] | None = None    # (name, exe)


def _pick_player(preferred: str | None = None) -> tuple[str, str] | None:
    """
    Return (name, exe_path) for the player to use.
    Priority: preferred > cached > mpv > vlc.
    """
    global _cached_player

    available = detect_players()
    if not available:
        return None

    # Explicit preference
    if preferred:
        # preferred may be a name ("mpv") or a full path
        p_lower = preferred.lower()
        if p_lower in available:
            exe = available[p_lower]
            _cached_player = (p_lower, exe)
            return _cached_player
        # Maybe it's a path
        p_path = Path(preferred)
        if p_path.exists() and p_path.is_file():
            name = p_path.stem.lower()
            _cached_player = (name, str(p_path))
            return _cached_player

    # Cached from a previous call
    if _cached_player and _cached_player[1] == available.get(_cached_player[0]):
        return _cached_player

    # mpv > vlc
    for name in ("mpv", "vlc"):
        if name in available:
            _cached_player = (name, available[name])
            return _cached_player

    return None


# ===================================================================
# Stream URL parsing
# ===================================================================

def _parse_stream_url(stream_url: str) -> tuple[str, dict]:
    """Split 'url|Header1=val1&Header2=val2' into (url, headers_dict)."""
    if "|" not in stream_url:
        return stream_url, {}
    url, header_part = stream_url.split("|", 1)
    headers = {}
    for item in header_part.split("&"):
        if "=" in item:
            k, v = item.split("=", 1)
            headers[k.strip()] = unquote(v)
    return url, headers


# ===================================================================
# Launch
# ===================================================================

def _play_mpv(exe: str, url: str, headers: dict, title: str | None) -> bool:
    from .config import PLAYER_ARGS

    cmd = [exe] + list(PLAYER_ARGS)
    if title:
        cmd.append(f"--force-media-title={title}")
    if headers:
        hdr = ",".join(f"{k}: {v}" for k, v in headers.items())
        cmd.append(f"--http-header-fields={hdr}")
    cmd.append(url)

    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        err(f"mpv executable not found at: {exe}")
        return False
    except KeyboardInterrupt:
        info("playback interrupted.")
    return True


def _play_vlc(exe: str, url: str, headers: dict, title: str | None) -> bool:
    from .config import PLAYER_ARGS

    cmd = [exe] + list(PLAYER_ARGS) + ["--no-video-title-show"]
    if "Referer" in headers:
        cmd.append(f"--http-referrer={headers['Referer']}")
    if "User-Agent" in headers:
        cmd.append(f"--http-user-agent={headers['User-Agent']}")
    cmd.append(url)

    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        err(f"vlc executable not found at: {exe}")
        return False
    except KeyboardInterrupt:
        info("playback interrupted.")
    return True


def play(stream_url: str, title: str | None = None,
         player: str | None = None) -> bool:
    """Play a single stream URL. Blocks until the player exits."""
    from .config import PLAYER as CONFIG_PLAYER

    picked = _pick_player(preferred=player or CONFIG_PLAYER)
    if not picked:
        err("No supported player found.")
        info("Run the setup again to download mpv, or install one manually:")
        info("  mpv: https://mpv.io/installation/")
        info("  vlc: https://www.videolan.org/vlc/")
        return False

    name, exe = picked
    url, headers = _parse_stream_url(stream_url)
    info(f"playing in [bold]{name}[/]: {title or url}")

    try:
        if name == "mpv":
            return _play_mpv(exe, url, headers, title)
        if name == "vlc":
            return _play_vlc(exe, url, headers, title)
    except Exception as e:
        err(f"player failed: {e}")
        return False
    return False


def play_sequential(episodes, language: str, series_url: str,
                    player: str | None = None) -> None:
    """Resolve and play each episode in turn."""
    from .resolver import get_stream_url
    from .filenames import build_filename

    total = len(episodes)
    failed = 0

    for i, item in enumerate(episodes, 1):
        name = build_filename(item, series_url)
        console.print()
        console.print(f"[bold bright_green]({i}/{total})[/] {name}")

        try:
            stream = get_stream_url(item.url, language)
        except Exception as e:
            err(f"resolve failed: {e}")
            failed += 1
            continue

        try:
            play(stream, title=name, player=player)
        except Exception as e:
            err(f"playback failed: {e}")
            failed += 1

    if failed:
        warn(f"{failed} episode(s) failed.")
    else:
        ok(f"finished {total} episode(s).")
