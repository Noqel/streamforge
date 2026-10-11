# src/streamforge/sites/aniworld.py
import re
from html import unescape
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from ..config import ANIME_BASE, LANG_KEY_MAP
from ..models import SearchResult, Episode, LanguageChoice
from .base import Site


def _clean(text):
    return unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


class AniWorldSite(Site):
    name = "AniWorld"
    domains = ("aniworld.to",)
    languages = (
        LanguageChoice("GER-DUB", "German Dub",   "German audio"),
        LanguageChoice("GER-SUB", "German Sub",   "Japanese audio, German subs"),
        LanguageChoice("ENG-SUB", "Japanese Sub", "Japanese audio, English subs"),
    )
    aliases = {}   # AniWorld uses the canonical hoster names as-is

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
            cls._session = s
        return cls._session

    # ---------------------------------------------------------------
    # Search
    # ---------------------------------------------------------------
    def search(self, query):
        r = self.session().post(
            f"{ANIME_BASE}/ajax/search",
            data={"keyword": query},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{ANIME_BASE}/",
            },
            timeout=15,
        )
        r.raise_for_status()
        if not r.text.strip():
            return []
        try:
            data = r.json()
        except ValueError:
            return []
        if isinstance(data, dict):
            data = [data]

        results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            link = item.get("link", "")
            if not re.match(r"^/anime/stream/[^/]+/?$", link):
                continue
            results.append(SearchResult(
                title=_clean(item.get("title", "")),
                url=ANIME_BASE + link,
                description=_clean(item.get("description", "")),
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

        nav = soup.find("div", class_="hosterSiteDirectNav")
        ul = nav.find("ul") if nav else None
        if not ul:
            return [("season", series_url, "Staffel 1")]

        links = []
        for a in ul.find_all("a", href=True):
            href = a["href"]
            label = a.get_text(strip=True)
            if "staffel-" in href:
                links.append(("season", ANIME_BASE + href, label))
            elif "/filme" in href:
                links.append(("movie", ANIME_BASE + href, label))
        return links or [("season", series_url, "Staffel 1")]

    def _episodes_for(self, page_url):
        r = self.session().get(page_url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        table = soup.find("table", class_="seasonEpisodesList")
        tbody = table.find("tbody") if table else None
        if not tbody:
            return []

        entries = []
        for tr in tbody.find_all("tr"):
            td_first = tr.find("td")
            if not td_first:
                continue
            a = td_first.find("a", href=True)
            if not a:
                continue

            url = ANIME_BASE + a["href"]
            num_text = (a.get_text(strip=True)
                        .replace("Folge", "").replace("Film", "").strip())
            try:
                num = int(num_text)
            except ValueError:
                num = None

            title = None
            tds = tr.find_all("td")
            if len(tds) > 1:
                title_a = tds[1].find("a")
                if title_a:
                    title = title_a.get_text(strip=True)

            entries.append({"url": url, "episode": num, "title": title})
        return entries

    # ---------------------------------------------------------------
    # Hoster redirect
    # ---------------------------------------------------------------
    def resolve_hoster(self, episode_url, hoster_name, language):
        r = self.session().get(episode_url, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        key_for = {v: k for k, v in LANG_KEY_MAP.items()}

        # German Dub falls back to German Sub if not available
        chain = ["GER-DUB", "GER-SUB"] if language == "GER-DUB" else [language]

        redirect_path = None
        for lang in chain:
            key = key_for.get(lang)
            if not key:
                continue
            for li in soup.find_all("li", attrs={"data-lang-key": key}):
                icon = li.find("i", class_=hoster_name)
                if not icon:
                    continue
                path = li.get("data-link-target")
                if not path:
                    a = li.find("a", href=True)
                    path = a["href"] if a else None
                if path:
                    redirect_path = path
                    break
            if redirect_path:
                break

        if not redirect_path:
            return None

        if redirect_path.startswith("/"):
            redirect_url = "https://" + urlparse(episode_url).netloc + redirect_path
        else:
            redirect_url = redirect_path

        r2 = self.session().get(redirect_url, allow_redirects=True, timeout=30)
        return r2.url