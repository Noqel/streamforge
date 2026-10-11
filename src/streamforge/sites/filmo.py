# src/streamforge/sites/filmo.py
import re
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup

from ..config import FILMO_BASE
from ..models import SearchResult, Episode, LanguageChoice
from .base import Site


# data-language-label on the provider button → internal code
_FILMO_LANG_MAP = {
    "deutsch":  "GER-DUB",
    "german":   "GER-DUB",
    "englisch": "ENG-SUB",
    "english":  "ENG-SUB",
}


class FilmoSite(Site):
    name = "Filmo"
    domains = ("filmo.to",)
    languages = (
        LanguageChoice("GER-DUB", "German",  "German audio"),
        LanguageChoice("ENG-SUB", "English", "English audio"),
    )
    # Filmo calls the Filemoon backend "Byse"
    aliases = {"Filemoon": "Byse"}

    _session = None

    @classmethod
    def session(cls):
        if cls._session is None:
            s = requests.Session()
            s.headers.update({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            })
            try:
                s.get(FILMO_BASE + "/", timeout=15)
            except Exception:
                pass
            cls._session = s
        return cls._session

    # ---------------------------------------------------------------
    # Search
    # ---------------------------------------------------------------
    def search(self, query):
        r = self.session().get(
            f"{FILMO_BASE}/search/suggest",
            params={"q": query},
            headers={
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{FILMO_BASE}/",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        results = []
        for item in data.get("movies", []):
            url = item.get("url", "")
            if not url:
                continue
            results.append(SearchResult(
                title=item.get("title", ""),
                url=url,
                source=self.name,
            ))
        return results

    # ---------------------------------------------------------------
    # Episode list — Filmo movies are a single item
    # ---------------------------------------------------------------
    def build_episode_list(self, series_url):
        return [Episode(url=series_url, type="movie")]

    # ---------------------------------------------------------------
    # Hoster redirect
    # ---------------------------------------------------------------
    def resolve_hoster(self, episode_url, hoster_name, language):
        r = self.session().get(episode_url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        provider = self._pick_provider(soup, hoster_name, language)
        if not provider:
            return None

        # Two response shapes exist depending on the Filmo version:
        #   1) data-play-url → "/r?t=<token>"  (current)
        #   2) data-p        → POST to /n     (older)
        if provider.get("play_url"):
            return self._follow_r(provider["play_url"], episode_url)
        if provider.get("token"):
            x = self._mint_x(provider["token"], episode_url)
            if not x:
                return None
            return self._follow_n(x, episode_url)
        return None

    # ---------------------------------------------------------------
    # Provider parsing
    # ---------------------------------------------------------------
    def _pick_provider(self, soup, hoster_name, language):
        """
        Return the best matching button as a dict:
        {provider, language, play_url, token, auto}
        """
        # Buttons can appear either as <button class="link-box"> or
        # <div class="provider-chip">. Collect everything that has a
        # provider name and either a play-url or a data-p token.
        elements = soup.find_all(["button", "div"], class_=True)

        candidates = []
        for el in elements:
            classes = el.get("class") or []
            if isinstance(classes, str):
                classes = [classes]
            if not any(c in ("link-box", "provider-chip") for c in classes):
                continue

            provider = (el.get("data-provider-name")
                        or el.get("aria-label")
                        or "").strip()
            if not provider:
                # fall back to the chip's name span
                name_el = el.find("span", class_="provider-chip__name")
                if name_el:
                    provider = name_el.get_text(strip=True)
            if not provider:
                continue

            # Filter by hoster
            if provider.lower() != hoster_name.lower():
                continue

            play_url = el.get("data-play-url")
            token = el.get("data-p")
            if not play_url and not token:
                continue

            lang_label = (el.get("data-language-label") or "").strip().lower()
            lang = _FILMO_LANG_MAP.get(lang_label)

            candidates.append({
                "provider": provider,
                "language": lang,
                "play_url": play_url,
                "token":    token,
                "auto":     el.has_attr("data-auto-select"),
            })

        if not candidates:
            return None

        # Prefer the requested language, but fall back to any candidate
        # (Filmo files are typically dual-audio anyway).
        matches = [c for c in candidates if c["language"] == language]
        if not matches:
            matches = candidates

        # Prefer the auto-select chip if one exists
        for c in matches:
            if c["auto"]:
                return c
        return matches[0]

    # ---------------------------------------------------------------
    # /r?t=... flow (current Filmo)
    # ---------------------------------------------------------------
    def _follow_r(self, play_url, referer):
        url = play_url if play_url.startswith("http") else FILMO_BASE + play_url

        headers = {
            "Referer":         referer,
            "Sec-Fetch-Dest":  "iframe",
            "Sec-Fetch-Mode":  "navigate",
            "Sec-Fetch-Site":  "same-origin",
        }
        xsrf = self.session().cookies.get("XSRF-TOKEN")
        if xsrf:
            headers["X-XSRF-TOKEN"] = unquote(xsrf)

        r = self.session().get(url, headers=headers,
                                allow_redirects=False, timeout=30)

        if r.status_code in (301, 302, 303, 307, 308):
            return r.headers.get("Location")

        # Sometimes the response is a meta-refresh page
        m = re.search(
            r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+url=[\'"]?([^\'"\s>]+)',
            r.text, re.I,
        )
        if m:
            return m.group(1)

        # Byse sometimes wraps the target in <a class="open" href="...">
        m = re.search(
            r'<a[^>]+class=["\'][^"\']*\bopen\b[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
            r.text, re.I,
        )
        if m:
            return m.group(1)

        return None

    # ---------------------------------------------------------------
    # /n API flow (older Filmo)
    # ---------------------------------------------------------------
    def _mint_x(self, token, referer):
        xsrf = self.session().cookies.get("XSRF-TOKEN")

        headers = {
            "Referer":          referer,
            "Origin":           FILMO_BASE,
            "X-Requested-With": "XMLHttpRequest",
            "Accept":           "application/json, text/plain, */*",
            "Content-Type":     "application/x-www-form-urlencoded",
            "Sec-Fetch-Dest":   "empty",
            "Sec-Fetch-Mode":   "cors",
            "Sec-Fetch-Site":   "same-origin",
        }
        if xsrf:
            headers["X-XSRF-TOKEN"] = unquote(xsrf)

        r = self.session().post(f"{FILMO_BASE}/n", data={"p": token},
                                 headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        try:
            return r.json().get("x")
        except ValueError:
            return None

    def _follow_n(self, x, referer):
        url = f"{FILMO_BASE}/n/{x}"
        headers = {
            "Referer":         referer,
            "Sec-Fetch-Dest":  "iframe",
            "Sec-Fetch-Mode":  "navigate",
            "Sec-Fetch-Site":  "same-origin",
        }
        r = self.session().get(url, headers=headers,
                                allow_redirects=False, timeout=15)

        if r.status_code in (301, 302, 303, 307, 308):
            return r.headers.get("Location")

        m = re.search(
            r'<a[^>]+class=["\'][^"\']*\bopen\b[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
            r.text, re.I,
        )
        if m:
            return m.group(1)

        m = re.search(
            r'<meta[^>]+http-equiv=["\'][^>]+refresh["\'][^>]+url=[\'"]?([^\'"\s>]+)',
            r.text, re.I,
        )
        if m:
            return m.group(1)

        return None