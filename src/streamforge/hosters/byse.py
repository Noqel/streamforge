# src/streamforge/hosters/byse.py
from .base import Hoster


class ByseHoster(Hoster):
    # Canonical name — this is what `resolver.py` iterates over.
    name = "Filemoon"
    # Alternative names that sites may use to refer to the same backend.
    aliases = ("Byse",)

    def extract(self, url):
        from ._byse_impl import extract
        return extract(url)