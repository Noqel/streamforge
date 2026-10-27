# -*- coding: utf-8 -*-
"""
Setup for mpv (MSVC build) + Anime4K.

Strategy (portable-first):
  1. Download the official MSVC ZIP build -> tools/mpv/
  2. Extract mpv.exe + DLLs
  3. Check for existing configs in %APPDATA%\\mpv\\ BEFORE writing anything
  4. Install Anime4K into tools/mpv/portable_config/

Portable configs override %APPDATA%\\mpv, so the user's global mpv
configuration is never touched.
"""

import io
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request


# ---- mpv: official git-release with MSVC ZIP assets ----
MPV_RELEASE_API = "https://api.github.com/repos/mpv-player/mpv/releases/tags/git-release"
MPV_ASSET_PATTERN = "x86_64-pc-windows-msvc.zip"

# ---- Anime4K ----
ANIME4K_TEMPLATES = {
    "low":  "https://github.com/Tama47/Anime4K/releases/download/v4.0.1/GLSL_Windows_Low-end.zip",
    "high": "https://github.com/Tama47/Anime4K/releases/download/v4.0.1/GLSL_Windows_High-end.zip",
}
ANIME4K_SHADERS_ZIP = (
    "https://github.com/bloc97/Anime4K/releases/download/v4.0.1/Anime4K_v4.0.zip"
)

# ---- Paths ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
MPV_DIR = TOOLS_DIR / "mpv"


# ===================================================================
# Helpers
# ===================================================================
# Shader chains for Anime4K Mode A
_MODE_A_HIGH = (
    "~~/shaders/Anime4K_Clamp_Highlights.glsl:"
    "~~/shaders/Anime4K_Restore_CNN_VL.glsl:"
    "~~/shaders/Anime4K_Upscale_CNN_x2_VL.glsl:"
    "~~/shaders/Anime4K_AutoDownscalePre_x2.glsl:"
    "~~/shaders/Anime4K_AutoDownscalePre_x4.glsl:"
    "~~/shaders/Anime4K_Upscale_CNN_x2_M.glsl"
)

_MODE_A_LOW = (
    "~~/shaders/Anime4K_Clamp_Highlights.glsl:"
    "~~/shaders/Anime4K_Restore_CNN_M.glsl:"
    "~~/shaders/Anime4K_Upscale_CNN_x2_M.glsl:"
    "~~/shaders/Anime4K_AutoDownscalePre_x2.glsl:"
    "~~/shaders/Anime4K_AutoDownscalePre_x4.glsl:"
    "~~/shaders/Anime4K_Upscale_CNN_x2_S.glsl"
)


def _patch_mpv_conf(config_dir: Path, variant: str):
    """
    Add/overwrite the startup options in mpv.conf:
      - volume=50
      - fullscreen=yes
      - glsl-shaders=<Mode A chain for the chosen variant>
    """
    mpv_conf = config_dir / "mpv.conf"
    if not mpv_conf.exists():
        mpv_conf.write_text("", encoding="utf-8")

    lines = mpv_conf.read_text(encoding="utf-8").splitlines()

    # Strip any existing versions of the three options (with or without --)
    strip_prefixes = (
        "volume=", "fullscreen=", "fs=",
        "glsl-shaders=",
    )
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if any(stripped.startswith(p) for p in strip_prefixes):
            continue
        cleaned.append(line)

    # Append the three options
    shader_chain = _MODE_A_HIGH if variant == "high" else _MODE_A_LOW
    cleaned.append("")
    cleaned.append("# --- StreamForge startup defaults ---")
    cleaned.append("hwdec=gpu")
    cleaned.append("volume=50")
    cleaned.append("fullscreen=yes")
    cleaned.append(f'glsl-shaders="{shader_chain}"')

    mpv_conf.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
    print(f"  patched mpv.conf (volume=50, fullscreen, Anime4K Mode A)")

def _download(url: str, label: str = "") -> bytes:
    if label:
        print(f"  downloading {label}...")
    req = Request(url, headers={"User-Agent": "StreamForge/2.0"})
    with urlopen(req, timeout=120) as resp:
        data = resp.read()
    if label:
        print(f"  got {len(data) // 1024 // 1024} MB")
    return data


def _extract_zip_bytes(data: bytes, target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(target_dir)


def _resolve_mpv_url() -> str:
    """Find the MSVC ZIP build in the git-release assets."""
    req = Request(
        MPV_RELEASE_API,
        headers={
            "User-Agent": "StreamForge/2.0",
            "Accept": "application/vnd.github+json",
        },
    )
    with urlopen(req, timeout=30) as resp:
        release = json.loads(resp.read().decode("utf-8"))

    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if MPV_ASSET_PATTERN in name:
            print(f"  selected asset: {name}")
            return asset["browser_download_url"]

    raise RuntimeError(
        f"No asset matching {MPV_ASSET_PATTERN!r}. "
        f"Available: {[a.get('name') for a in release.get('assets', [])]}"
    )


# ===================================================================
# mpv installation
# ===================================================================

def install_mpv(force: bool = False) -> Path:
    mpv_exe = MPV_DIR / "mpv.exe"

    if mpv_exe.exists() and not force:
        print(f"  mpv already installed: {mpv_exe}")
        return mpv_exe

    print("Resolving latest MSVC build via GitHub API...")
    url = _resolve_mpv_url()
    data = _download(url, "mpv (MSVC)")

    if data[:2] != b"PK":
        raise RuntimeError(
            "Downloaded file is not a ZIP. The API may have returned "
            "an unexpected asset."
        )

    _extract_zip_bytes(data, MPV_DIR)

    # Flatten if the archive nests inside a subfolder
    candidates = list(MPV_DIR.rglob("mpv.exe"))
    if not candidates:
        raise RuntimeError("mpv.exe not found in the downloaded archive.")

    src_exe = candidates[0]
    if src_exe.parent != MPV_DIR:
        for f in src_exe.parent.iterdir():
            target = MPV_DIR / f.name
            if target.exists():
                if target.is_file():
                    target.unlink()
                else:
                    shutil.rmtree(target)
            shutil.move(str(f), str(target))
        shutil.rmtree(src_exe.parent, ignore_errors=True)

    print(f"  mpv installed: {MPV_DIR / 'mpv.exe'}")
    return MPV_DIR / "mpv.exe"


# ===================================================================
# Config discovery
# ===================================================================

def find_existing_configs() -> dict:
    """
    Return every place mpv configs are found:
      {'global': {...}, 'portable': {...}}
    """
    result = {"global": {}, "portable": {}}

    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        appdata = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    global_dir = appdata / "mpv"

    for name in ("mpv.conf", "input.conf"):
        p = global_dir / name
        if p.exists():
            result["global"][name] = p

    portable_dir = MPV_DIR / "portable_config"
    for name in ("mpv.conf", "input.conf"):
        p = portable_dir / name
        if p.exists():
            result["portable"][name] = p

    return result


def _print_config_report(configs: dict):
    print()
    print("Existing mpv configs:")
    if not configs["global"] and not configs["portable"]:
        print("  (none found)")
        return
    for scope, files in configs.items():
        if not files:
            continue
        print(f"  {scope}:")
        for name, path in files.items():
            print(f"    {name}: {path}")


# ===================================================================
# Anime4K installation
# ===================================================================

def install_anime4k(variant: str = "low", target: str = "portable",
                     force: bool = False):
    """
    Install Anime4K shaders + configs.

    target: 'portable' -> tools/mpv/portable_config/  (recommended)
            'global'   -> %APPDATA%\\mpv\\
    """
    if variant not in ANIME4K_TEMPLATES:
        raise ValueError("variant must be 'low' or 'high'")

    configs = find_existing_configs()
    _print_config_report(configs)

    if target == "portable":
        config_dir = MPV_DIR / "portable_config"
    else:
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        config_dir = base / "mpv"

    existing = configs.get(target, {})
    if existing and not force:
        print()
        print(f"[!] {target} config already contains:")
        for name, path in existing.items():
            print(f"    {name}  ({path})")
        answer = input("Overwrite? Existing files will be renamed to *.bak [y/N]: ")
        if answer.strip().lower() != "y":
            print("  skipped -- existing configs left untouched.")
            return config_dir

    # Backup existing files
    config_dir.mkdir(parents=True, exist_ok=True)
    for name in ("mpv.conf", "input.conf"):
        p = config_dir / name
        if p.exists():
            bak = p.with_suffix(p.suffix + ".bak")
            if bak.exists():
                bak.unlink()
            shutil.move(str(p), str(bak))
            print(f"  backed up {name} -> {bak.name}")

    # ---- Download Anime4K template ----
    print(f"Downloading Anime4K template ({variant})...")
    tpl = _download(ANIME4K_TEMPLATES[variant], "template")

    tmp_dir = config_dir / ".anime4k_tmp"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    _extract_zip_bytes(tpl, tmp_dir)

    for name in ("mpv.conf", "input.conf"):
        src = tmp_dir / name
        if not src.exists():
            matches = list(tmp_dir.rglob(name))
            if matches:
                src = matches[0]
        if src.exists():
            shutil.move(str(src), str(config_dir / name))
            print(f"  installed {name}")

    # ---- Patch mpv.conf with startup defaults ----
    _patch_mpv_conf(config_dir, variant)

    # ---- Download Anime4K shaders ----
    print("Downloading Anime4K shaders...")
    shader_zip = _download(ANIME4K_SHADERS_ZIP, "shaders")

    shader_dir = config_dir / "shaders"
    shader_dir.mkdir(parents=True, exist_ok=True)
    _extract_zip_bytes(shader_zip, shader_dir)

    # Flatten any nested subfolders
    for p in list(shader_dir.rglob("*.glsl")):
        if p.parent != shader_dir:
            target_file = shader_dir / p.name
            if target_file.exists():
                target_file.unlink()
            shutil.move(str(p), str(target_file))

    # Clean up empty subdirs
    for p in sorted(shader_dir.rglob("*"), reverse=True):
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)

    count = len(list(shader_dir.glob("*.glsl")))
    print(f"  installed {count} shader(s)")
    print()
    print(f"Anime4K ready in: {config_dir}")
    return config_dir


# ===================================================================
# Uninstall
# ===================================================================

def uninstall():
    """Remove Anime4K files from the portable config and restore backups."""
    portable_dir = MPV_DIR / "portable_config"
    if not portable_dir.exists():
        print("  nothing to uninstall (no portable_config).")
        return

    shader_dir = portable_dir / "shaders"
    if shader_dir.exists():
        removed = 0
        for p in shader_dir.glob("Anime4K_*.glsl"):
            p.unlink()
            removed += 1
        print(f"  removed {removed} Anime4K shader(s)")

    for name in ("mpv.conf", "input.conf"):
        bak = portable_dir / (name + ".bak")
        if bak.exists():
            target = portable_dir / name
            if target.exists():
                target.unlink()
            shutil.move(str(bak), str(target))
            print(f"  restored {name} from backup")

    print("Anime4K uninstalled.")


# ===================================================================
# CLI
# ===================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Install mpv and Anime4K for StreamForge.")
    parser.add_argument("--mpv-only", action="store_true",
                        help="Only download mpv, skip Anime4K")
    parser.add_argument("--anime4k-only", action="store_true",
                        help="Only install Anime4K (mpv must already be present)")
    parser.add_argument("--variant", choices=["low", "high"], default="low",
                        help="GPU tier for Anime4K (default: low)")
    parser.add_argument("--target", choices=["portable", "global"], default="portable",
                        help="Where to install configs (default: portable)")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing configs without asking")
    parser.add_argument("--uninstall", action="store_true",
                        help="Remove Anime4K from the portable config")
    args = parser.parse_args()

    if args.uninstall:
        uninstall()
        sys.exit(0)

    if not args.anime4k_only:
        try:
            install_mpv(force=args.force)
        except Exception as e:
            print(f"[ERROR] mpv download failed: {e}")
            print("  Manual fallback: https://github.com/mpv-player/mpv/releases/tag/git-release")
            sys.exit(1)

    if not args.mpv_only:
        try:
            install_anime4k(
                variant=args.variant,
                target=args.target,
                force=args.force,
            )
        except Exception as e:
            print(f"[ERROR] Anime4K install failed: {e}")
            sys.exit(1)
