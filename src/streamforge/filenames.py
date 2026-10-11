# src/streamforge/filenames.py
import re
from html import unescape

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Windows: 255 chars per path component, 260 for the full path.
# Reserve room for the extension and the Downloads\ prefix.
_MAX_FILENAME = 200

_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def _clean_text(s):
    """Remove HTML tags and decode entities from any scraped string."""
    if not s:
        return ""
    s = _TAG_RE.sub("", s)
    s = unescape(s)
    s = unescape(s)
    return s.strip()


def sanitize_filename(name):
    name = _clean_text(name)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = _WS_RE.sub(" ", name).strip(" .")

    if name.upper() in _RESERVED_NAMES:
        name = f"_{name}"

    if len(name) > _MAX_FILENAME:
        cut = name[:_MAX_FILENAME].rsplit(" ", 1)[0]
        if len(cut) > _MAX_FILENAME * 0.7:
            name = cut
        else:
            name = name[:_MAX_FILENAME]
        name = name.rstrip(" .")

    return name or "untitled"


def build_filename(item, series_url):
    """
    Build the base filename (without extension and without the [LANG] tag).
    `item` is an Episode dataclass with .type, .season, .episode, .title.
    """
    if item.type == "episode":
        slug = series_url.rstrip("/").split("/")[-1]
        anime_name = _clean_text(slug.replace("-", " ")).title()
        s = item.season or 0
        e = item.episode or 0
        name = f"{anime_name} S{s:02d}E{e:02d}"

        if item.title:
            # Leave room for " [GER-DUB].mp4" = 15 chars
            budget = _MAX_FILENAME - len(name) - 15
            title = _clean_text(item.title)
            if budget > 5 and len(title) > budget:
                cut = title[:budget].rsplit(" ", 1)[0]
                title = cut or title[:budget]
            if title:
                name += f" - {title}"
    else:
        name = _clean_text(item.title) or _clean_text(
            series_url.rstrip("/").split("/")[-1]
        )

    return sanitize_filename(name)