#!/usr/bin/env python3
"""
STREAMFORGE
Multi-source stream downloader for AniWorld, SerienStream, and Filmo.
"""

import re
import time
from html import unescape
import base64, hashlib, json, re, time
from urllib.parse import urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup
import yt_dlp
import cloudscraper
from pathlib import Path
from urllib.parse import urlparse

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    DownloadColumn, TransferSpeedColumn, TimeRemainingColumn,
)
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from byse_extractor import extract
from voe_extractor import extract_voe as extract_voe_direct


_HACKER_THEME = Theme({
    "info":     "bold bright_green",
    "ok":       "bold green",
    "warn":     "bold yellow",
    "err":      "bold red",
    "prompt":   "bold bright_green",
    "accent":   "bright_green",
    "dimtext":  "green",
    "title":    "bold bright_green",
})

console = Console(theme=_HACKER_THEME)
ANIME_BASE       = "https://aniworld.to"
SERIENSTREAM_BASE = "https://serienstream.to"
FILMO_BASE = "https://filmo.to"
_ss_session = None
_ss_last_warm = 0.0
_filmo_session = None
VERSION = "2.0.0"


# ===================================================================
# Banner & logging
# ===================================================================

BANNER = r"""
  ███████╗████████╗██████╗ ███████╗ █████╗ ███╗   ███╗███████╗ ██████╗ ██████╗  ██████╗ ███████╗
  ██╔════╝╚══██╔══╝██╔══██╗██╔════╝██╔══██╗████╗ ████║██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
  ███████╗   ██║   ██████╔╝█████╗  ███████║██╔████╔██║█████╗  ██║   ██║██████╔╝██║  ███╗█████╗
  ╚════██║   ██║   ██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝
  ███████║   ██║   ██║  ██║███████╗██║  ██║██║ ╚═╝ ██║██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
  ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
"""


def show_banner():
    console.print(BANNER, style="bold bright_green", highlight=False)
    console.print(Align.center(
        Text(">> multi-source stream downloader  ·  aniworld · serienstream · filmo",
             style="bold green")
    ))
    console.print(Align.center(
        Text(f"version {VERSION}  ·  running on {__import__('platform').system()}  ·  session secured",
             style="dim green")
    ))
    console.print()


def info(msg):  console.print(f"[bold bright_green][*][/] {msg}")
def ok(msg):    console.print(f"[bold green][+][/] {msg}")
def warn(msg):  console.print(f"[bold yellow][!][/] {msg}")
def err(msg):   console.print(f"[bold red][x][/] {msg}")

DOWNLOADS_DIR = Path("Downloads")

def _base_of(url):
    """Return scheme://host for any URL."""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"

def ensure_downloads_dir():
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return DOWNLOADS_DIR


def section(title):
    line = "─" * 72
    console.print()
    console.print(f"[bright_green]┌──[/][bold bright_green] [ {title.upper()} ] [/][bright_green]{line}[/]")
    console.print()

# ===================================================================
# Search
# ===================================================================

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE  = re.compile(r"\s+")
# ---- Language handling ------------------------------------------------
# data-lang-key → human label, from AniWorld's episode page <li> wrappers
_LANG_KEY_MAP = {
    "1": "GER-DUB",
    "2": "ENG-SUB",
    "3": "GER-SUB",
}


def _clean(text):
    return unescape(_TAG_RE.sub("", text or "")).strip()
    
def _get_filmo_session():
    global _filmo_session
    if _filmo_session is None:
        _filmo_session = requests.Session()
        _filmo_session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })
        try:
            _filmo_session.get(FILMO_BASE + "/", timeout=15)
        except Exception:
            pass
    return _filmo_session


def _search_filmo(query):
    resp = _get_filmo_session().get(
        f"{FILMO_BASE}/search/suggest",
        params={"q": query},
        headers={
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{FILMO_BASE}/",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    movies = []
    for item in data.get("movies", []):
        url = item.get("url", "")
        if not url:
            continue
        movies.append({
            "title":       _clean(item.get("title", "")),
            "description": "",
            "url":         url,
        })
    return movies
    
def _get_ss_session(force_warm=False):
    """Shared SerienStream session. Re-warms if it's been a while or on demand."""
    import time
    global _ss_session, _ss_last_warm

    if _ss_session is None:
        _ss_session = requests.Session()
        _ss_session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })

    # Refresh DDoS-Guard cookies if stale (> 10 min) or forced
    if force_warm or (time.time() - _ss_last_warm > 600):
        try:
            _ss_session.get(
                "https://serienstream.to/",
                headers={"Referer": "https://serienstream.to/"},
                timeout=15,
            )
            _ss_last_warm = time.time()
        except Exception:
            pass

    return _ss_session


def search_series(query, per_site=10):
    """Query all three sites; return up to `per_site` results from each, tagged with source."""
    combined = []

    sources = (
        ("AniWorld",     _search_aniworld),
        ("SerienStream", _search_serienstream),
        ("Filmo",        _search_filmo),
    )

    console.print()
    for name, fn in sources:
        try:
            hits = fn(query) or []
            hits = hits[:per_site]
            for h in hits:
                h["source"] = name
            if hits:
                console.print(
                    f"  [green]✓[/] [bold]{name:<12}[/] [dim]{len(hits)} hit(s)[/]"
                )
            else:
                console.print(
                    f"  [dim]○[/] [dim]{name:<12} no results[/]"
                )
            combined.extend(hits)
        except Exception as e:
            msg = str(e).splitlines()[0][:60]
            console.print(
                f"  [red]✗[/] [bold]{name:<12}[/] [dim red]{msg}[/]"
            )

    return combined


def _search_aniworld(query):
    resp = requests.post(
        f"{ANIME_BASE}/ajax/search",
        data={"keyword": query},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{ANIME_BASE}/",
        },
        timeout=15,
    )
    resp.raise_for_status()

    # Empty body = no results. Return an empty list instead of crashing.
    if not resp.text.strip():
        return []

    try:
        results = resp.json()
    except ValueError:
        # Some servers return non-JSON error pages for zero hits.
        return []

    if isinstance(results, dict):
        results = [results]
    if not isinstance(results, list):
        return []

    series = []
    for item in results:
        if not isinstance(item, dict):
            continue
        link = item.get("link", "")
        if not re.match(r"^/anime/stream/[^/]+/?$", link):
            continue
        series.append({
            "title":       _clean(item.get("title")),
            "description": _clean(item.get("description")),
            "url":         ANIME_BASE + link,
        })
    return series


def _search_serienstream(query):
    """GET https://serienstream.to/api/search/suggest?term=<query>"""
    resp = requests.get(
        f"{SERIENSTREAM_BASE}/api/search/suggest",
        params={"term": query},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{SERIENSTREAM_BASE}/",
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    series = []
    for item in data.get("shows", []):
        url = item.get("url", "")
        # SerienStream series links look like /serie/<slug>
        if not re.match(r"^/serie/[^/]+/?$", url):
            continue
        series.append({
            "title":       _clean(item.get("name", "")),   # note: "name", not "title"
            "description": "",                              # not provided by this endpoint
            "url":         SERIENSTREAM_BASE + url,
        })
    return series


# ===================================================================
# AniWorld scraping
# ===================================================================

# =====================================================================
#  Site-specific scraping (AniWorld vs SerienStream)
# =====================================================================

def _is_serienstream(url):
    return "serienstream" in url


def _http_get(url):
    if "serienstream.to" in url:
        return _get_ss_session().get(url, timeout=15)
    if "filmo.to" in url:
        return _get_filmo_session().get(url, timeout=15)
    # AniWorld and anything else: plain requests
    return requests.get(
        url, timeout=15,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
    )


# ---------------------------- Season links ---------------------------

def get_season_links(series_url):
    base = _base_of(series_url)
    resp = _http_get(series_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    if _is_serienstream(series_url):
        return _season_links_ss(soup, base, series_url)
    return _season_links_aw(soup, base, series_url)


def _season_links_aw(soup, base, series_url):
    """AniWorld: div.hosterSiteDirectNav > ul > a"""
    nav_div = soup.find("div", class_="hosterSiteDirectNav")
    ul = nav_div.find("ul") if nav_div else None
    if not ul:
        return [("season", series_url, "Staffel 1")]

    links = []
    for a in ul.find_all("a", href=True):
        href = a["href"]
        label = a.get_text(strip=True)
        if "staffel-" in href:
            links.append(("season", base + href, label))
        elif "/filme" in href:
            links.append(("movie", base + href, label))
    return links or [("season", series_url, "Staffel 1")]


def _season_links_ss(soup, base, series_url):
    """SerienStream: anchors with class 'nav-link' pointing at /serie/<slug>/staffel-N."""
    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # /serie/<slug>/staffel-<digits>  and nothing after
        if not re.match(r"^/serie/[^/]+/staffel-\d+/?$", href):
            continue
        if href in seen:
            continue
        seen.add(href)

        label = a.get_text(strip=True)

        # staffel-0 with label "Filme" is the movie bucket
        if "/staffel-0" in href or "film" in label.lower():
            links.append(("movie", base + href, label or "Filme"))
        else:
            links.append(("season", base + href, label or href))

    return links or [("season", series_url, "Staffel 1")]


# --------------------------- Episode rows ----------------------------

def get_entries_from_page(page_url):
    base = _base_of(page_url)
    resp = _http_get(page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    if _is_serienstream(page_url):
        return _entries_ss(soup, base, page_url)   # <-- pass page_url
    return _entries_aw(soup, base)


def _entries_aw(soup, base):
    """AniWorld: table.seasonEpisodesList > tbody > tr, first <td> has the episode link."""
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

        url = base + a["href"]
        num_text = (a.get_text(strip=True)
                     .replace("Folge", "")
                     .replace("Film", "")
                     .strip())
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


def _entries_ss(soup, base, page_url):
    """SerienStream: table.episode-table; episode URL is constructed from season + row number."""
    table = (soup.find("table", class_="episode-table")
             or soup.find("table", class_="seasonEpisodesList"))
    if not table:
        return []

    # --- Derive season slug from the page URL we fetched ---
    # page_url looks like: https://serienstream.to/serie/<slug>/staffel-N
    m = re.search(r"(/serie/[^/]+/staffel-\d+)", page_url)
    if not m:
        return []
    season_path = m.group(1)              # "/serie/game-of-thrones/staffel-1"

    tbody = table.find("tbody") or table
    entries = []

    for tr in tbody.find_all("tr"):
        # Skip header rows
        if tr.find("th", attrs={"scope": "col"}):
            continue
        if tr.find("th", attrs={"scope": "row"}) is None and tr.find("th") is None:
            # No row header -> not a data row
            continue

        # --- Episode number ---
        num = None

        # 1) <th scope="row">N</th>  (most common Laravel table pattern)
        th = tr.find("th", attrs={"scope": "row"})
        if th:
            try:
                num = int(th.get_text(strip=True))
            except ValueError:
                num = None

        # 2) Fallback: first cell
        if num is None:
            first = tr.find(["td", "th"])
            if first:
                try:
                    num = int(first.get_text(strip=True))
                except ValueError:
                    num = None

        if num is None:
            continue

        # --- Title: second cell, best effort ---
        title = None
        cells = tr.find_all(["td", "th"])
        if len(cells) >= 2:
            txt = cells[1].get_text(" ", strip=True)
            # Clean up "Wo anschauen" / hoster gibberish if it got concatenated
            if txt and txt != str(num):
                # Drop language / hoster noise often tacked on the end
                txt = re.sub(r"\s*(VOE|Vidmoly|Streamtape|StreamTape|Doodstream|"
                             r"Filemoon|Mixdrop|Vidoza)\s*", " ", txt).strip()
                title = txt or None

        # --- Construct the URL ---
        url = base + season_path + f"/episode-{num}"

        entries.append({
            "url":     url,
            "episode": num,
            "title":   title,
        })

    return entries


# --------------------------- Orchestrator ----------------------------

def _is_filmo(url):
    return "filmo.to" in url


def build_episode_list(series_url):
    # Filmo: single-item "list"
    if _is_filmo(series_url):
        return [{
            "url":     series_url,
            "type":    "movie",
            "season":  None,
            "episode": None,
            "title":   None,
        }]

    # AniWorld / SerienStream
    all_items = []
    for typ, url, label in get_season_links(series_url):
        match = re.search(r"(\d+)", label or "")
        season_num = int(match.group(1)) if match else None

        for entry in get_entries_from_page(url):
            is_movie = (typ == "movie")
            all_items.append({
                "url":     entry["url"],
                "type":    "movie" if is_movie else "episode",
                "season":  None if is_movie else season_num,
                "episode": entry["episode"],
                "title":   entry["title"],
            })
    return all_items


# ===================================================================
# Hoster redirect + stream extraction
# ===================================================================



def _solve_altcha(challenge, salt, maxnumber):
    """Find n such that SHA256(salt + str(n)) == challenge (hex)."""
    target = challenge.lower()
    salt = str(salt)
    for n in range(int(maxnumber) + 1):
        if hashlib.sha256(f"{salt}{n}".encode()).hexdigest() == target:
            return n
    return None


def _extract_csrf(soup):
    """Laravel CSRF token — meta tag or hidden input."""
    meta = soup.find("meta", attrs={"name": "csrf-token"})
    if meta and meta.get("content"):
        return meta["content"]
    inp = soup.find("input", attrs={"name": "_token"})
    if inp and inp.get("value"):
        return inp["value"]
    return None


def _resolve_filmo_episode(base, movie_url, hoster_class, language):
    session = _get_filmo_session()

    # On Filmo, Filemoon is called "Byse". Same backend, different name.
    if hoster_class == "Filemoon":
        hoster_class = "Byse"

    resp = session.get(movie_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    providers = _parse_filmo_providers(soup)
    if not providers:
        return None

    pool = [p for p in providers if p["hoster"].lower() == hoster_class.lower()]
    if not pool:
        return None

    # Use the user's language choice. Fall back to any chip in the pool
    # if that language isn't offered for this movie.
    matches = [p for p in pool if p["language"] == language] or pool
    chosen = next((p for p in matches if p["auto"]), matches[0])

    return _resolve_filmo(session, base, chosen["token"], movie_url,
                          hoster=chosen["hoster"])


def _resolve_filmo(session, base, token, referer, hoster=""):
    """Exchange token at /n, then resolve /n/<x>.
       - VOE returns a 302 with the hoster URL in Location.
       - Byse returns an HTML page with <a class="open" href="...">.
    """
    # ---- Laravel CSRF header ----
    xsrf = session.cookies.get("XSRF-TOKEN")
    headers = {
        "Referer":          referer,
        "Origin":           base,
        "X-Requested-With": "XMLHttpRequest",
        "Accept":           "application/json, text/plain, */*",
        "Sec-Fetch-Dest":   "empty",
        "Sec-Fetch-Mode":   "cors",
        "Sec-Fetch-Site":   "same-origin",
        "Content-Type":     "application/x-www-form-urlencoded",
    }
    if xsrf:
        headers["X-XSRF-TOKEN"] = unquote(xsrf)

    # ---- Step 1: token -> x ----
    r = session.post(
        f"{base}/n",
        data={"p": token},
        headers=headers,
        timeout=15,
    )
    if r.status_code != 200:
        warn(f"Filmo /n returned {r.status_code}: {r.text[:200]}")
        return None

    try:
        x = r.json().get("x")
    except ValueError:
        warn(f"Filmo /n returned non-JSON: {r.text[:200]}")
        return None

    if not x:
        warn("Filmo /n response missing 'x'")
        return None

    # ---- Step 2: GET /n/<x> ----
    r2 = session.get(
        f"{base}/n/{x}",
        headers={
            "Referer":         referer,
            "Accept":          "text/html,application/xhtml+xml,application/xml;"
                               "q=0.9,*/*;q=0.8",
            "Sec-Fetch-Dest":  "iframe",
            "Sec-Fetch-Mode":  "navigate",
            "Sec-Fetch-Site":  "same-origin",
        },
        allow_redirects=False,
        timeout=15,
    )

    # Case A: 3xx redirect (VOE and friends)
    if r2.status_code in (301, 302, 303, 307, 308):
        loc = r2.headers.get("Location")
        if loc:
            return loc

    # Case B: HTML page with the hoster link (Byse)
    m = re.search(
        r'<a[^>]+class=["\'][^"\']*\bopen\b[^"\']*["\'][^>]+href=["\']([^"\']+)["\']',
        r2.text, re.I,
    )
    if m:
        return m.group(1)

    # Case C: meta-refresh (some hosters)
    m = re.search(
        r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+url=[\'"]?([^\'"\s>]+)',
        r2.text, re.I,
    )
    if m:
        return m.group(1)

    warn(f"Filmo /n/<x> returned {r2.status_code}, no hoster link found")
    return None


def _resolve_serienstream_via_altcha(session, base, play_url, episode_url, soup):
    """Solve Altcha PoW, POST to /r, return the 302 Location."""
    token = parse_qs(urlparse(play_url).query).get("t", [None])[0]
    if not token:
        raise Exception("No 't' token in data-play-url")

    csrf = _extract_csrf(soup)
    if not csrf:
        raise Exception("Couldn't find Laravel _token on episode page")

    # --- 1. Fetch the challenge ---
    r = session.get(
        f"{base}/api/inline/verify-init",
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

    # --- 2. Solve ---
    t0 = time.time()
    number = _solve_altcha(ch["challenge"], ch["salt"], ch["maxnumber"])
    took_ms = int((time.time() - t0) * 1000)
    if number is None:
        raise Exception("Altcha PoW had no solution within maxnumber")

    # --- 3. Build the base64 blob Altcha expects ---
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

    # --- 4. POST to /r ---
    r2 = session.post(
        f"{base}/r",
        data={
            "_token": csrf,
            "t":      token,
            "altcha": altcha_b64,
        },
        headers={
            "Accept":         "text/html,application/xhtml+xml,application/xml;"
                              "q=0.9,*/*;q=0.8",
            "Content-Type":   "application/x-www-form-urlencoded",
            "Origin":         base,
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

    raise Exception(
        f"/r returned {r2.status_code} ({len(r2.text)} bytes). "
        f"Body starts: {r2.text[:300]}"
    )
    
    
def pick_language(for_aniworld=False):
    """
    Ask the user to pick a language.
    - AniWorld: German Dub / German Sub / Japanese Sub  (3 distinct variants)
    - Filmo / SerienStream: German / English (dub/sub not distinguished)
    Returns the internal language code.
    """
    if for_aniworld:
        choices = [
            ("GER-DUB", "German Dub",   "German audio"),
            ("GER-SUB", "German Sub",   "Japanese audio, German subs"),
            ("ENG-SUB", "Japanese Sub", "Japanese audio, English subs"),
        ]
    else:
        choices = [
            ("GER-DUB", "German",  "German audio track"),
            ("ENG-SUB", "English", "English audio track"),
        ]

    table = Table(
    box=box.SIMPLE_HEAVY,          # statt ROUNDED
    border_style="bright_green",   # statt bright_black
    header_style="bold bright_green",
    padding=(0, 1),
    )
    table.add_column("#",        style="bold yellow", justify="right", width=4)
    table.add_column("Language", style="bold white")
    table.add_column("Info",     style="dim")

    for i, (code, label, desc) in enumerate(choices, 1):
        suffix = "  [dim](default)[/]" if i == 1 else ""
        table.add_row(str(i), f"{label}{suffix}", desc)

    console.print()
    console.print(table)
    console.print()

    while True:
        choice = Prompt.ask(
            f"[bold bright_green]$[/] Pick language [bold](1-{len(choices)})[/]",
            default="1",
        ).strip()
        try:
            idx = int(choice)
            if 1 <= idx <= len(choices):
                return choices[idx - 1][0]
        except ValueError:
            pass
        warn("Invalid choice.")
        
# -------------------------------------------------------------------------
# AniWorld resolver — unchanged logic, just extracted
# -------------------------------------------------------------------------
def _resolve_aniworld(session, episode_url, soup, hoster_class, language):
    def _find_redirect_path(lang_key):
        for li in soup.find_all("li", attrs={"data-lang-key": lang_key}):
            if not li.find("i", class_=hoster_class):
                continue
            path = li.get("data-link-target")
            if path:
                return path
            a = li.find("a", href=True)
            if a:
                return a["href"]
        return None

    key_for = {v: k for k, v in _LANG_KEY_MAP.items()}
    chain = ["GER-DUB", "GER-SUB"] if language == "GER-DUB" else [language]

    redirect_path = None
    for lang in chain:
        redirect_path = _find_redirect_path(key_for[lang])
        if redirect_path:
            if lang != language:
                warn(f"{language} not available — falling back to {lang}.")
            break

    if not redirect_path:
        return None

    if redirect_path.startswith("/"):
        redirect_url = "https://" + episode_url.split("/")[2] + redirect_path
    else:
        redirect_url = redirect_path

    resp2 = session.get(redirect_url, allow_redirects=True, timeout=30)
    return resp2.url


# -------------------------------------------------------------------------
# SerienStream resolver — the new one
# -------------------------------------------------------------------------
def _pick_ss_button(soup, hoster_class, language):
    """Return the <button class='link-box'> for the given hoster + language."""
    buttons = soup.find_all("button", class_="link-box")

    candidates = []
    for btn in buttons:
        provider = (btn.get("data-provider-name") or "").strip()
        if provider.lower() != hoster_class.lower():
            continue
        if not btn.get("data-play-url"):
            continue
        candidates.append(btn)

    if not candidates:
        return None

    # Prefer the button whose language matches what the user asked for
    for btn in candidates:
        if _ss_button_matches_language(btn, language):
            return btn

    # No match — fall back to the first one (no warning)
    return candidates[0]


def _ss_button_matches_language(btn, language):
    """SerienStream gives the language on the button itself — use it directly."""
    lang_id    = (btn.get("data-language-id") or "").strip()
    lang_label = (btn.get("data-language-label") or "").strip().lower()

    # Map data-language-id → internal language codes
    #   1 = Deutsch  → GER-DUB / GER-SUB
    #   2 = Englisch → ENG-SUB
    id_map = {
        "1": ("GER-DUB", "GER-SUB"),
        "2": ("ENG-SUB",),
    }

    if lang_id in id_map and language in id_map[lang_id]:
        return True

    # Fallback: match on the label text
    if language in ("GER-DUB", "GER-SUB") and "deutsch" in lang_label:
        return True
    if language == "ENG-SUB" and "englisch" in lang_label:
        return True

    # Last-resort: check the SVG flag href (#icon-flag-german / #icon-flag-english)
    for use in btn.find_all("use", href=True):
        h = use["href"].lower()
        if language in ("GER-DUB", "GER-SUB") and "german" in h:
            return True
        if language == "ENG-SUB" and "english" in h:
            return True

    return False


def _resolve_serienstream(session, base, soup, hoster_class, language,
                          episode_url=None):
    btn = _pick_ss_button(soup, hoster_class, language)
    if not btn:
        return None

    play_url = btn["data-play-url"]
    full_url = base + play_url if play_url.startswith("/") else play_url

    # First attempt: some episodes still redirect directly (tier=none or altcha-only)
    r = session.get(
        full_url,
        allow_redirects=False,
        headers={
            "Referer":         episode_url or base + "/",
            "Sec-Fetch-Dest":  "iframe",
            "Sec-Fetch-Mode":  "navigate",
            "Sec-Fetch-Site":  "same-origin",
        },
        timeout=30,
    )
    if r.status_code in (301, 302, 303, 307, 308):
        return r.headers.get("Location")

    # Otherwise solve Altcha and POST /r
    return _resolve_serienstream_via_altcha(
        session, base, play_url, episode_url, soup
    )

        
def get_hoster_redirect(episode_url, hoster_class="Filemoon", language="GER-DUB"):
    base = _base_of(episode_url)

    # ---- Filmo: different flow (movie page + /n API) ----
    if _is_filmo(episode_url):
        return _resolve_filmo_episode(base, episode_url, hoster_class, language)

    # ---- Pick the session based on the site ----
    is_ss = "serienstream" in base

    if is_ss:
        session = _get_ss_session()
    else:
        # AniWorld
        session = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 OPR/133.0.0.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9,de-DE;q=0.8,de;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "iframe",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Upgrade-Insecure-Requests": "1",
            "Referer": episode_url,
        })

    # ---- Fetch the episode page ----
    resp = session.get(episode_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # ---- Dispatch to the site-specific resolver ----
    if is_ss:
        return _resolve_serienstream(
            session, base, soup, hoster_class, language,
            episode_url=episode_url,
        )
    return _resolve_aniworld(session, episode_url, soup, hoster_class, language)


def extract_voe(voe_url):
    try:
        return extract_voe_direct(voe_url)
    except Exception as e:
        warn(f"Standalone VOE resolver failed: {e}")
        info("Falling back to yt-dlp for VOE...")
        ydl_opts = {"quiet": True, "no_warnings": True, "format": "best"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_data = ydl.extract_info(voe_url, download=False)
            if "url" in info_data:
                return info_data["url"]
            if "formats" in info_data:
                best = max(info_data["formats"], key=lambda f: f.get("height", 0) or 0)
                return best.get("url")
        return None


def get_stream_url(episode_url, language="GER-DUB"):
    for hoster in ("Filemoon", "VOE"):
        info(f"Trying [bold]{hoster}[/] [dim]({language})[/]...")
        try:
            redirect_url = get_hoster_redirect(episode_url, hoster, language)
            if not redirect_url:
                warn(f"{hoster} not found for {language}.")
                continue

            if hoster == "Filemoon":
                return extract(redirect_url)
            if hoster == "VOE":
                stream = extract_voe(redirect_url)
                if stream:
                    return stream
                warn("VOE extraction failed.")
        except Exception as e:
            err(f"Error with {hoster}: {e}")

    raise Exception(f"No working stream found for this episode in {language}.")

_FILMO_LANG_MAP = {
    "Deutsch": "GER-DUB",
    "German":  "GER-DUB",
    "English": "ENG-SUB",
    "Englisch": "ENG-SUB",
}


def _parse_filmo_providers(soup):
    """Return a list of {hoster, language, token, link_id, quality} dicts."""
    providers = []

    for row in soup.find_all("div", class_="provider-row"):
        # --- Language of this row ---
        language = None

        lang_label = row.find("span", class_="provider-row__lang")
        if lang_label:
            language = _FILMO_LANG_MAP.get(lang_label.get_text(strip=True))

        if not language:
            # Fall back to the flag class: <span class="fi fi-de">
            flag = row.find("span", class_=lambda c: c and any(
                x.startswith("fi-") and x != "fi" for x in (c if isinstance(c, list) else [c])
            ))
            if flag:
                for cls in flag.get("class", []):
                    if cls.startswith("fi-") and cls != "fi":
                        code = cls[3:]
                        language = {
                            "de": "GER-DUB",
                            "gb": "ENG-SUB",
                            "us": "ENG-SUB",
                        }.get(code)

        # --- Chips inside this row ---
        chips = row.find("div", class_="provider-row__chips")
        if not chips:
            continue

        for chip in chips.find_all("div", class_="provider-chip"):
            token = chip.get("data-p")
            if not token:
                continue

            hoster = chip.get("aria-label")
            if not hoster:
                name_el = chip.find("span", class_="provider-chip__name")
                hoster = name_el.get_text(strip=True) if name_el else ""

            quality = ""
            meta = chip.find_all("span", class_="provider-chip__metadata-tag")
            if meta:
                quality = " ".join(t.get_text(strip=True) for t in meta)

            providers.append({
                "hoster":   hoster,
                "language": language,
                "token":    token,
                "link_id":  chip.get("data-movie-link-id"),
                "quality":  quality,
                "auto":     chip.has_attr("data-auto-select"),
            })

    return providers


# ===================================================================
# Download with progress bar
# ===================================================================
from html import unescape


def _clean_text(s):
    """Remove HTML tags and decode entities from any scraped string."""
    if not s:
        return ""
    s = _TAG_RE.sub("", s)   # <em>Chainsaw Man</em> → Chainsaw Man
    s = unescape(s)          # &amp; → &, &#8230; → …, &quot; → "
    s = unescape(s)          # second pass for double-encoded entities
    return s.strip()
    
# Windows: 255 chars per path component, 260 for the full path.
# We reserve room for the extension and the Downloads\ prefix.
_MAX_FILENAME = 200


def sanitize_filename(name):
    name = _clean_text(name)
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = _WS_RE.sub(" ", name).strip(" .")   # collapse whitespace, no trailing dots/spaces

    # Windows reserves these device names — avoid them entirely
    _RESERVED = {"CON", "PRN", "AUX", "NUL",
                 "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
                 "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if name.upper() in _RESERVED:
        name = f"_{name}"

    if len(name) > _MAX_FILENAME:
        # Truncate on a word boundary if possible
        cut = name[:_MAX_FILENAME].rsplit(" ", 1)[0]
        name = (cut if len(cut) > _MAX_FILENAME * 0.7 else name[:_MAX_FILENAME]).rstrip(" .")

    return name or "untitled"


def build_filename(item, series_url):
    """
    Build the base filename (without extension and without the [LANG] tag).
    The final length cap is applied in sanitize_filename, but we also trim
    the title part here so the language tag has room to breathe.
    """
    if item["type"] == "episode":
        slug = series_url.rstrip("/").split("/")[-1]
        anime_name = _clean_text(slug.replace("-", " ")).title()
        s = item["season"] or 0
        e = item["episode"] or 0
        name = f"{anime_name} S{s:02d}E{e:02d}"
        if item["title"]:
            # Leave room for " [GER-DUB].mp4" = 15 chars
            budget = _MAX_FILENAME - len(name) - 15
            title = _clean_text(item["title"])
            if budget > 5 and len(title) > budget:
                cut = title[:budget].rsplit(" ", 1)[0]
                title = cut or title[:budget]
            if title:
                name += f" - {title}"
    else:
        name = _clean_text(item["title"]) or _clean_text(series_url.rstrip("/").split("/")[-1])

    return sanitize_filename(name)
    
# ===================================================================
# Language → ISO code mapping for yt-dlp audio track selection
# ===================================================================
_LANG_TO_ISO = {
    "GER-DUB": "de",
    "GER-SUB": "de",
    "ENG-SUB": "en",
}


# ===================================================================
# Download with progress bar
# ===================================================================
def download_hls(stream_url, output_filename, audio_lang=None):
    # ---- Split URL from the header suffix (Byse/VOE style) ----
    if "|" in stream_url:
        url_part, header_part = stream_url.split("|", 1)
        headers = {}
        for item in header_part.split("&"):
            if "=" in item:
                k, v = item.split("=", 1)
                headers[k.strip()] = unquote(v)
    else:
        url_part, headers = stream_url, {}

    # ---- Format chain (handles AniWorld combined + Filmo split streams) ----
    if audio_lang:
        fmt = (
            f"bestvideo+bestaudio[language={audio_lang}]"
            f"/bestvideo+bestaudio"
            f"/best"
        )
    else:
        fmt = "bestvideo+bestaudio/best"

    short_name = output_filename
    if len(short_name) > 55:
        short_name = short_name[:52] + "..."

    progress = Progress(
    SpinnerColumn(style="bright_green"),
    TextColumn("[bold bright_green]{task.description}"),
    BarColumn(bar_width=None, complete_style="bright_green", finished_style="green"),
    DownloadColumn(),
    TextColumn("[bright_green]{task.fields[speed_text]:>12}[/]"),
    TextColumn("[green]{task.fields[eta_text]:>10}[/]"),
    console=console,
        )

    with progress:
        task = progress.add_task(
            short_name,
            total=None,
            speed_text="",
            eta_text="",
        )

        def hook(d):
            status = d.get("status")
            if status == "downloading":
                total      = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                speed      = d.get("speed")          # bytes/s, may be None
                eta        = d.get("eta")            # seconds, may be None

                # Speed text
                if speed and speed > 0:
                    if speed >= 1024 * 1024:
                        speed_text = f"{speed / 1024 / 1024:.2f} MiB/s"
                    else:
                        speed_text = f"{speed / 1024:.0f} KiB/s"
                else:
                    speed_text = ""

                # ETA text
                if eta is not None and eta >= 0:
                    eta = int(eta)
                    h, rem = divmod(eta, 3600)
                    m, s = divmod(rem, 60)
                    if h:
                        eta_text = f"{h}:{m:02d}:{s:02d}"
                    else:
                        eta_text = f"{m:02d}:{s:02d}"
                else:
                    eta_text = ""

                update_kwargs = {
                    "completed":  downloaded,
                    "speed_text": speed_text,
                    "eta_text":   eta_text,
                }
                if total:
                    update_kwargs["total"] = total
                progress.update(task, **update_kwargs)

            elif status == "finished":
                progress.update(
                    task,
                    description=f"[green]{short_name}[/]",
                    speed_text="[green]done[/]",
                    eta_text="",
                )

        ydl_opts = {
            "outtmpl":      output_filename,
            "quiet":        True,
            "no_warnings":  True,
            "noprogress":   True,
            "http_headers": headers,
            "format":       fmt,
            "merge_output_format": "mp4",
            "progress_hooks": [hook],
            "concurrent_fragment_downloads": 16,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_part])


# ===================================================================
# Batch download
# ===================================================================
        
def run_downloads(selected, series_url, language="GER-DUB"):
    section("Downloads")
    ensure_downloads_dir()

    total = len(selected)
    success = failed = 0

    # yt-dlp audio-track filter — German or English only
    audio_iso = _LANG_TO_ISO.get(language)

    for i, item in enumerate(selected, 1):
        url = item["url"]
        filename = f"{build_filename(item, series_url)} [{language}]"
        output_path = DOWNLOADS_DIR / f"{filename}.mp4"

        console.print()
        console.print(f"[bold cyan]({i}/{total})[/] [bold]{filename}[/]")

        try:
            stream = get_stream_url(url, language=language)
            download_hls(stream, str(output_path), audio_lang=audio_iso)
            ok(f"Saved: [bold]{output_path}[/]")
            success += 1
        except Exception as e:
            err(f"Failed: {e}")
            failed += 1

        if i < total:
            time.sleep(5)

    section("Summary")
    console.print(f"  [bold green]✓[/] {success} downloaded")
    if failed:
        console.print(f"  [bold red]✗[/] {failed} failed")


# ===================================================================
# Interactive UI
# ===================================================================

def pick_series():
    """Return (url, title) — title is None when the user pasted a URL."""
    console.print("[bold]What do you want to download?[/]")
    console.print("[dim]Type a series name to search, or paste a full AniWorld URL.[/]")
    console.print()

    query = Prompt.ask("[bold bright_green]$[/]").strip()
    if not query:
        warn("No input provided.")
        return None, None

    if query.startswith(("http://", "https://")):
        return query, None

    with console.status(f"[cyan]Searching for [bold]{query}[/]...", spinner="dots"):
        try:
            results = search_series(query)
        except Exception as e:
            err(f"Search failed: {e}")
            return None, None

    if not results:
        warn(f"No series found for [bold]{query}[/].")
        return None, None

    table = Table(
    box=box.SIMPLE_HEAVY,          # statt ROUNDED
    border_style="bright_green",   # statt bright_black
    header_style="bold bright_green",
    padding=(0, 1),
    )
    table.add_column("#",      style="bold yellow", justify="right", width=4)
    table.add_column("Title",  style="bold white")
    table.add_column("Source", style="magenta", width=14)
    table.add_column("Slug",   style="dim")

    for i, r in enumerate(results, 1):
        source = r.get("source", "?")
        slug = r["url"].split("/", 3)[-1] if "/" in r["url"] else r["url"]
        table.add_row(str(i), r["title"], source, slug)

    console.print()
    console.print(table)
    console.print()

    while True:
        choice = Prompt.ask(
            f"[bold bright_green]$[/] Pick [bold](1-{len(results)})[/] or [bold]q[/] to quit"
        ).strip()
        if choice.lower() in ("q", "quit", "exit"):
            return None, None
        try:
            idx = int(choice)
            if 1 <= idx <= len(results):
                r = results[idx - 1]
                return r["url"], r["title"]
        except ValueError:
            pass
        warn("Invalid choice.")


def display_episodes(items):
    table = Table(
    box=box.SIMPLE_HEAVY,          # statt ROUNDED
    border_style="bright_green",   # statt bright_black
    header_style="bold bright_green",
    padding=(0, 1),
    )
    table.add_column("#", style="bold yellow", justify="right", width=5)
    table.add_column("S / E", style="magenta", width=10)
    table.add_column("Title", style="white")

    for i, item in enumerate(items, 1):
        if item["type"] == "episode":
            s = f"S{item['season']:02d}" if item["season"] else "S??"
            e = f"E{item['episode']:02d}" if item["episode"] else "E??"
            tag = f"{s} {e}"
        else:
            tag = "[yellow]MOVIE[/]"

        table.add_row(str(i), tag, item.get("title") or "—")

    console.print(table)


def pick_items(items):
    console.print()
    console.print("[bold]What to download?[/]")
    console.print("  [bold cyan]1[/]  Single item")
    console.print("  [bold cyan]2[/]  Everything")
    console.print("  [bold cyan]3[/]  Range  [dim](e.g. 1-5)[/]")
    console.print()

    while True:
        choice = Prompt.ask("[bold bright_green]$[/]").strip()
        if choice == "1":
            n = IntPrompt.ask(f"[bold bright_green]$[/] Item number (1-{len(items)})")
            if 1 <= n <= len(items):
                return [items[n - 1]]
            warn("Out of range.")
        elif choice == "2":
            return items
        elif choice == "3":
            rng = Prompt.ask("[bold bright_green]$[/] Range [dim](e.g. 1-5)[/]").strip()
            try:
                a, b = rng.split("-")
                a, b = int(a), int(b)
                if 1 <= a <= b <= len(items):
                    return items[a - 1:b]
            except Exception:
                pass
            warn("Invalid range.")
        else:
            warn("Invalid choice.")


def pick_hoster():
    console.print()
    console.print("[bold]Preferred hoster?[/]")
    console.print("  [bold cyan]1[/]  Filemoon  [dim](default)[/]")
    console.print("  [bold cyan]2[/]  VOE")
    console.print()
    choice = Prompt.ask("[bold bright_green]$[/]", default="1").strip()
    return "VOE" if choice == "2" else "Filemoon"

# ===================================================================
# Entry point
# ===================================================================

def main():
    ensure_downloads_dir()

    while True:
        console.clear()
        show_banner()

        try:
            series_url, series_title = pick_series()
            if series_url is None:
                break

            if series_title:
                ok(f"Selected: [bold]{series_title}[/]")

            # ---- Language -------------------------------------------------
            is_aw = not (_is_filmo(series_url) or _is_serienstream(series_url))
            section("Language")
            language = pick_language(for_aniworld=is_aw)
            ok(f"Language: [bold]{language}[/]")

            # ---- Episode list ---------------------------------------------
            console.print()
            console.print(Rule(style="bright_green"))
            if series_title:
                console.print(Align.center(Text(f"› {series_title} ‹", style="bold cyan")))
            section("Episode list")

            with console.status("[cyan]Fetching episode list...", spinner="dots"):
                try:
                    items = build_episode_list(series_url)
                except Exception as e:
                    err(f"Failed to build episode list: {e}")
                    _pause()
                    continue

            if not items:
                warn("No episodes or movies found for this series.")
                _pause()
                continue

            ok(f"Found [bold]{len(items)}[/] items")
            display_episodes(items)

            if _is_filmo(series_url) or len(items) == 1:
                selected = items
                info(f"Single item — auto-selected: [bold]{items[0]['url']}[/]")
            else:
                selected = pick_items(items)
                if not selected:
                    _pause()
                    continue

            run_downloads(selected, series_url, language)

        except KeyboardInterrupt:
            console.print()
            warn("Cancelled.")
            break
        except Exception as e:
            console.print()
            err(str(e))
            _pause()
            continue

        console.print()
        if not Confirm.ask("[bold bright_green]$[/] Do another download?", default=True):
            break

    console.print()
    console.print(Rule(style="bright_black"))
    console.print(Align.center(Text("Thanks for using STREAMFORGE 💜", style="bold magenta")))
    console.print()


def _pause():
    """Small pause so the user can read errors before the loop restarts."""
    console.print()
    Prompt.ask("[dim]Press Enter to continue[/]", default="", show_default=False)


if __name__ == "__main__":
    main()