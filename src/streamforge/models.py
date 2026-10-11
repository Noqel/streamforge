from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    description: str = ""
    source: str = ""


@dataclass
class Episode:
    url: str
    type: str                 # "episode" | "movie"
    season: int | None = None
    episode: int | None = None
    title: str | None = None


@dataclass
class LanguageChoice:
    code: str                 # internal code, e.g. "GER-DUB"
    label: str                # human label, e.g. "German"
    hint: str = ""            # optional description shown in the picker