# src/streamforge/config.py
from pathlib import Path

VERSION = "2.0.0"

ANIME_BASE        = "https://aniworld.to"
SERIENSTREAM_BASE = "https://serienstream.to"
FILMO_BASE        = "https://filmo.to"

DOWNLOADS_DIR = Path("Downloads")

# AniWorld: data-lang-key on episode page
LANG_KEY_MAP = {
    "1": "GER-DUB",
    "2": "ENG-SUB",
    "3": "GER-SUB",
}

# yt-dlp audio track filter
LANG_TO_ISO = {
    "GER-DUB": "de",
    "GER-SUB": "de",
    "ENG-SUB": "en",
}

# ===================================================================
# Player configuration
# ===================================================================
# PLAYER: "mpv", "vlc", a full path to a player executable, or None
#         for auto-detection (portable mpv -> portable vlc -> PATH).
PLAYER = None

# Extra CLI flags passed to the player before the URL.
# Examples:
#   ["--fullscreen"]
#   ["--volume=80", "--fs-screen=0"]
PLAYER_ARGS = []
