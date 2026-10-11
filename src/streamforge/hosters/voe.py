# hosters/voe.py
from .base import Hoster


class VoeHoster(Hoster):
    name = "VOE"
    aliases = ()

    def extract(self, url):
        from ._voe_impl import extract_voe
        return extract_voe(url)