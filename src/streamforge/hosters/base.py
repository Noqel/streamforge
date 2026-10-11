from abc import ABC, abstractmethod


class Hoster(ABC):
    name: str = ""
    aliases: tuple[str, ...] = ()

    @abstractmethod
    def extract(self, url: str) -> str:
        """Resolve a hoster page URL to a direct stream URL."""

    @classmethod
    def accepts(cls, name: str) -> bool:
        n = name.lower()
        return n == cls.name.lower() or n in (a.lower() for a in cls.aliases)