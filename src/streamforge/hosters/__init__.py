# src/streamforge/hosters/__init__.py
from .byse import ByseHoster
from .voe import VoeHoster

ALL_HOSTERS = (
    ByseHoster(),
    VoeHoster(),
)


def find_hoster(name):
    for h in ALL_HOSTERS:
        if h.accepts(name):
            return h
    return None


def hoster_order_for(site):
    """Ordered list of hoster names to try, translated through site.aliases."""
    order = []
    for h in ALL_HOSTERS:
        order.append(site.aliases.get(h.name, h.name))
    return order