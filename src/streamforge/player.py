# src/streamforge/player.py
"""
Stream playback via mpv or vlc.

The resolver returns URLs in the form 'url|Header1=val1&Header2=val2'.
This module splits that, translates the headers to player-specific flags,
and launches the player as a subprocess.
"""

import shutil
import subprocess
from urllib.parse import unquote

from .ui import console, info, ok, warn, err


def _parse_stream_url(stream_url):
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


def detect_players():
    """Return a dict {name: path} for all installed players."""
    found = {}
    for name in ("mpv", "vlc"):
        path = shutil.which(name)
        if path:
            found[name] = path
    return found


_cached_player = None


def _pick_player(preferred=None):
    """Return the player to use: preferred > cached > mpv > vlc."""
    global _cached_player

    available = detect_players()
    if not available:
        err("No supported player found.")
        info("Install mpv:  https://mpv.io/installation/")
        info("Install vlc:  https://www.videolan.org/vlc/")
        return None

    if preferred and preferred in available:
        _cached_player = preferred
        return preferred
    if _cached_player in available:
        return _cached_player
    for name in ("mpv", "vlc"):
        if name in available:
            _cached_player = name
            return name

    return None


def _play_mpv(url, headers, title):
    from .config import PLAYER_ARGS
    cmd = ["mpv"] + list(PLAYER_ARGS)
    if title:
        cmd.append(f"--force-media-title={title}")
    if headers:
        hdr = ",".join(f"{k}: {v}" for k, v in headers.items())
        cmd.append(f"--http-header-fields={hdr}")
    cmd.append(url)

    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        err("mpv executable not found.")
        return False
    except KeyboardInterrupt:
        info("Playback interrupted.")
    return True


def _play_vlc(url, headers, title):
    from .config import PLAYER_ARGS
    cmd = ["vlc"] + list(PLAYER_ARGS) + ["--no-video-title-show"]
    if "Referer" in headers:
        cmd.append(f"--http-referrer={headers['Referer']}")
    if "User-Agent" in headers:
        cmd.append(f"--http-user-agent={headers['User-Agent']}")
    cmd.append(url)

    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        err("vlc executable not found.")
        return False
    except KeyboardInterrupt:
        info("Playback interrupted.")
    return True


def play(stream_url, title=None, player=None):
    """Play a single stream URL. Blocks until the player exits."""
    from .config import PLAYER as CONFIG_PLAYER

    chosen = _pick_player(preferred=player or CONFIG_PLAYER)
    if not chosen:
        return False

    url, headers = _parse_stream_url(stream_url)
    info(f"Playing in [bold]{chosen}[/]: {title or url}")

    try:
        if chosen == "mpv":
            return _play_mpv(url, headers, title)
        if chosen == "vlc":
            return _play_vlc(url, headers, title)
    except Exception as e:
        err(f"Player failed: {e}")
        return False
    return False


def play_sequential(episodes, language, series_url, player=None):
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
            err(f"Resolve failed: {e}")
            failed += 1
            continue

        try:
            play(stream, title=name, player=player)
        except Exception as e:
            err(f"Playback failed: {e}")
            failed += 1

    if failed:
        warn(f"{failed} episode(s) failed.")
    else:
        ok(f"Finished {total} episode(s).")