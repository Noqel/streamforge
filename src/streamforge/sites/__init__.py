# src/streamforge/sites/__init__.py
from .aniworld import AniWorldSite
from .filmo import FilmoSite
from .serienstream import SerienStreamSite

ALL_SITES = (
    AniWorldSite(),
    SerienStreamSite(),
    FilmoSite(),
)


def find_site(url):
    for site in ALL_SITES:
        if site.matches(url):
            return site
    return None