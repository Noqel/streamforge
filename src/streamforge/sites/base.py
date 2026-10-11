from abc import ABC, abstractmethod
from ..models import SearchResult, Episode, LanguageChoice


class Site(ABC):
    name: str = ""
    domains: tuple[str, ...] = ()
    languages: tuple[LanguageChoice, ...] = ()
    aliases: dict[str, str] = {}       # hoster name on THIS site -> canonical hoster name

    def matches(self, url: str) -> bool:
        return any(d in url for d in self.domains)

    # --- required ---
    @abstractmethod
    def search(self, query: str) -> list[SearchResult]: ...

    @abstractmethod
    def build_episode_list(self, series_url: str) -> list[Episode]: ...

    @abstractmethod
    def resolve_hoster(self, episode_url: str, hoster_name: str,
                       language: str) -> str | None:
        """Return the redirect URL to the hoster, or None."""