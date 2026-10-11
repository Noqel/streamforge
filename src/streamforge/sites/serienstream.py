# src/streamforge/sites/serienstream.py
import base64
import hashlib
import json
import re
import socket
import time
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup

from ..config import SERIENSTREAM_BASE
from ..models import SearchResult, Episode, LanguageChoice
from .base import Site


# ===================================================================
# DNS over HTTPS — resolves serienstream.to even when system DNS is
# blocked or filtered. Uses Cloudflare (primary) and Google (fallback).
# No API key required. The monkey-patch below is applied at import.
# ===================================================================

_orig_getaddrinfo = socket.getaddrinfo
_dns_cache: dict[str, tuple[str, float]] = {}   # hostname → (ip, timestamp)
_DNS_TTL = 300                                   # re-resolve every 5 minutes

_DOH_ENDPOINTS = (
    ("https://cloudflare-dns.com/dns-query",
     {"Accept": "application/dns-json"}),
    ("https://dns.google/resolve",
     {"Accept": "application/dns-json"}),
)


def _resolve_via_doh(hostname):
    """Return the first A-record IP for hostname, or None."""
    for url, headers in _DOH_ENDPOINTS:
        try:
            r = requests.get(
                url,
                params={"name": hostname, "type": "A"},
                headers=headers,
                timeout=5,
            )
            r.raise_for_status()
            for answer in r.json().get("Answer", []):
                if answer.get("type") == 1:
                    return answer["data"]
        except Exception:
            continue
    return None


def _patched_getaddrinfo(host, *args, **kwargs):
    """
    Intercept DNS lookups for the domains we care about and route them
    through DoH. Everything else passes through unchanged.
    """
    if host in ("serienstream.to", "www.serienstream.to"):
        now = time.time()
        cached = _dns_cache.get(host)
        if not cached or (now - cached[1] > _DNS_TTL):
            ip = _resolve_via_doh(host)
            if ip:
                _dns_cache[host] = (ip, now)
        cached = _dns_cache.get(host)
        if cached:
            return _orig_getaddrinfo(cached[0], *args, **kwargs)
    return _orig_getaddrinfo(host, *args, **kwargs)


# Activate the patch for the whole process
socket.getaddrinfo = _patched_getaddrinfo


# ===================================================================
# Altcha PoW solver
# ===================================================================

def _solve_altcha(challenge, salt, maxnumber):
    """Find n such that SHA256(salt + str(n)) == challenge (hex)."""
    target = challenge.lower()
    salt = str(salt)
    for n in range(int(maxnumber) + 1):
        if hashlib.sha256(f"{salt}{n}".encode()).hexdigest() == target:
            return n
    return None


# SerienStream puts the language on the button itself:
#   data-language-id="1"  → Deutsch
#   data-language-id="2"  → Englisch
_SS_LANG_IDS = {
    "1": ("GER-DUB", "GER-SUB"),
    "2": ("ENG-SUB",),
}


class SerienStreamSite(Site):
    name = "SerienStream"
    domains = ("serienstream.to",)
    languages = (
        LanguageChoice("GER-DUB", "German",  "German audio"),
        LanguageChoice("ENG-SUB", "English", "English audio"),
    )
    aliases = {}

    _session = None
    _last_warm = 0.0

    # ---------------------------------------------------------------
    # Session with DDoS-Guard warmup
    # ---------------------------------------------------------------
    @classmethod
    def session(cls, force_warm=False):
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
            cls._session = s

        if force_warm or (time.time() - cls._last_warm > 600):
            try:
                cls._session.get(
                    SERIENSTREAM_BASE + "/",
                    headers={"Referer": SERIENSTREAM_BASE + "/"},
                    timeout=15,
                )
                cls._last_warm = time.time()
            except Exception:
                pass

        return cls._session

    # ---------------------------------------------------------------
    # Search
    # ---------------------------------------------------------------
    def search(self, query):
        r = self.session().get(
            f"{SERIENSTREAM_BASE}/api/search/suggest",
            params={"term": query},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{SERIENSTREAM_BASE}/",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        results = []
        for item in data.get("shows", []):
            url = item.get("url", "")
            if not re.match(r"^/serie/[^/]+/?$", url):
                continue
            results.append(SearchResult(
                title=item.get("name", ""),
                url=SERIENSTREAM_BASE + url,
                source=self.name,
            ))
        return results

    # ---------------------------------------------------------------
    # Episode list
    # ---------------------------------------------------------------
    def build_episode_list(self, series_url):
        episodes = []
        for typ, url, label in self._season_links(series_url):
            m = re.search(r"(\d+)", label or "")
            season_num = int(m.group(1)) if m else None
            for entry in self._episodes_for(url):
                is_movie = (typ == "movie")
                episodes.append(Episode(
                    url=entry["url"],
                    type="movie" if is_movie else "episode",
                    season=None if is_movie else season_num,
                    episode=entry["episode"],
                    title=entry["title"],
                ))
        return episodes

    def _season_links(self, series_url):
        r = self.session().get(series_url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        links = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not re.match(r"^/serie/[^/]+/staffel-\d+/?$", href):
                continue
            if href in seen:
                continue
            seen.add(href)

            label = a.get_text(strip=True)
            if "/staffel-0" in href or "film" in label.lower():
                links.append(("movie", SERIENSTREAM_BASE + href, label or "Filme"))
            else:
                links.append(("season", SERIENSTREAM_BASE + href, label or href))

        return links or [("season", series_url, "Staffel 1")]

    def _episodes_for(self, page_url):
        r = self.session().get(page_url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        table = (soup.find("table", class_="episode-table")
                 or soup.find("table", class_="seasonEpisodesList"))
        if not table:
            return []

        m = re.search(r"(/serie/[^/]+/staffel-\d+)", page_url)
        if not m:
            return []
        season_path = m.group(1)

        tbody = table.find("tbody") or table
        entries = []

        for tr in tbody.find_all("tr"):
            if tr.find("th", attrs={"scope": "col"}):
                continue

            num = None
            th = tr.find("th", attrs={"scope": "row"})
            if th:
                try:
                    num = int(th.get_text(strip=True))
                except ValueError:
                    pass
            if num is None:
                first = tr.find(["td", "th"])
                if first:
                    try:
                        num = int(first.get_text(strip=True))
                    except ValueError:
                        pass
            if num is None:
                continue

            title = None
            cells = tr.find_all(["td", "th"])
            if len(cells) >= 2:
                txt = cells[1].get_text(" ", strip=True)
                if txt and txt != str(num):
                    txt = re.sub(
                        r"\s*(VOE|Vidmoly|Streamtape|StreamTape|Doodstream|"
                        r"Filemoon|Mixdrop|Vidoza)\s*",
                        " ", txt,
                    ).strip()
                    title = txt or None

            entries.append({
                "url":     SERIENSTREAM_BASE + season_path + f"/episode-{num}",
                "episode": num,
                "title":   title,
            })

        return entries

    # ---------------------------------------------------------------
    # Hoster redirect
    # ---------------------------------------------------------------
    def resolve_hoster(self, episode_url, hoster_name, language):
        r = self.session().get(episode_url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        btn = self._pick_button(soup, hoster_name, language)
        if not btn:
            return None

        play_url = btn["data-play-url"]
        full_url = (SERIENSTREAM_BASE + play_url
                    if play_url.startswith("/") else play_url)

        r2 = self.session().get(
            full_url,
            allow_redirects=False,
            headers={
                "Referer":         episode_url,
                "Sec-Fetch-Dest":  "iframe",
                "Sec-Fetch-Mode":  "navigate",
                "Sec-Fetch-Site":  "same-origin",
            },
            timeout=30,
        )
        if r2.status_code in (301, 302, 303, 307, 308):
            return r2.headers.get("Location")

        return self._resolve_via_altcha(play_url, episode_url, soup)

    # ---------------------------------------------------------------
    # Button picking
    # ---------------------------------------------------------------
    def _pick_button(self, soup, hoster_name, language):
        buttons = soup.find_all("button", class_="link-box")

        candidates = []
        for btn in buttons:
            provider = (btn.get("data-provider-name") or "").strip()
            if provider.lower() != hoster_name.lower():
                continue
            if not btn.get("data-play-url"):
                continue
            candidates.append(btn)

        if not candidates:
            return None

        for btn in candidates:
            if self._button_matches_language(btn, language):
                return btn

        return candidates[0]

    def _button_matches_language(self, btn, language):
        lang_id = (btn.get("data-language-id") or "").strip()
        if lang_id in _SS_LANG_IDS and language in _SS_LANG_IDS[lang_id]:
            return True

        label = (btn.get("data-language-label") or "").strip().lower()
        if language in ("GER-DUB", "GER-SUB") and "deutsch" in label:
            return True
        if language == "ENG-SUB" and "englisch" in label:
            return True

        for use in btn.find_all("use", href=True):
            h = use["href"].lower()
            if language in ("GER-DUB", "GER-SUB") and "german" in h:
                return True
            if language == "ENG-SUB" and "english" in h:
                return True

        return False

    # ---------------------------------------------------------------
    # Altcha proof-of-work → POST /r
    # ---------------------------------------------------------------
    def _resolve_via_altcha(self, play_url, episode_url, soup):
        from urllib.parse import parse_qs

        token = parse_qs(urlparse(play_url).query).get("t", [None])[0]
        if not token:
            return None

        csrf = self._extract_csrf(soup)
        if not csrf:
            return None

        r = self.session().get(
            f"{SERIENSTREAM_BASE}/api/inline/verify-init",
            headers={
                "Accept":           "application/json, text/plain, */*",
                "Referer":          episode_url,
                "X-Requested-With": "XMLHttpRequest",
                "Sec-Fetch-Dest":   "empty",
                "Sec-Fetch-Mode":   "cors",
                "Sec-Fetch-Site":   "same-origin",
            },
            timeout=15,
        )
        r.raise_for_status()
        ch = r.json()

        t0 = time.time()
        number = _solve_altcha(ch["challenge"], ch["salt"], ch["maxnumber"])
        took_ms = int((time.time() - t0) * 1000)
        if number is None:
            return None

        payload = {
            "algorithm": ch["algorithm"],
            "challenge": ch["challenge"],
            "number":    number,
            "salt":      ch["salt"],
            "signature": ch["signature"],
            "took":      took_ms,
        }
        altcha_b64 = base64.b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode()

        r2 = self.session().post(
            f"{SERIENSTREAM_BASE}/r",
            data={"_token": csrf, "t": token, "altcha": altcha_b64},
            headers={
                "Accept":         "text/html,application/xhtml+xml,application/xml;"
                                  "q=0.9,*/*;q=0.8",
                "Content-Type":   "application/x-www-form-urlencoded",
                "Origin":         SERIENSTREAM_BASE,
                "Referer":        episode_url,
                "Sec-Fetch-Dest": "iframe",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Upgrade-Insecure-Requests": "1",
            },
            allow_redirects=False,
            timeout=30,
        )

        if r2.status_code in (301, 302, 303, 307, 308):
            return r2.headers.get("Location")
        return None

    @staticmethod
    def _extract_csrf(soup):
        meta = soup.find("meta", attrs={"name": "csrf-token"})
        if meta and meta.get("content"):
            return meta["content"]
        inp = soup.find("input", attrs={"name": "_token"})
        if inp and inp.get("value"):
            return inp["value"]
        return None