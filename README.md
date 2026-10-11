# StreamForge

A command-line downloader for streaming sources. Resolves hoster links,
handles proof-of-work captchas, and saves media files locally.

## Quick Start

**Windows**

1. Extract the ZIP.
2. Double-click `setup.bat` (installs everything, ~30 seconds).
3. Double-click `run.bat`.

**Other platforms**
pip install -r requirements.txt
pip install cython
python setup.py build_ext --inplace
python -m streamforge

Then follow the prompts: search, pick a result, pick a language, pick episodes.

## Overview

StreamForge queries multiple configured sources in parallel, resolves the
hoster links behind each entry, and downloads the resulting streams as MP4
files. It handles per-source authentication quirks, DDoS-Guard challenges,
proof-of-work captchas, and multi-audio-track selection transparently.

New sources and hosters can be added by dropping a single file into the
`sites/` or `hosters/` folder and registering it. No existing code needs
to change.

## Requirements

- Python 3.10 or newer (3.12 recommended)
- Windows 10/11 for the prebuilt package. Linux and macOS run from source.
- Internet connection

No C compiler, Nim toolchain, or build tools required for end users. The
proof-of-work extension ships precompiled for Windows 64-bit with Python 3.12.
On other platforms it is built once from source during setup.

## Usage

Run `run.bat` (Windows) or `python -m streamforge` (other platforms). The
program walks you through each step:

1. **Search** — type a title. All configured sources are queried and results
   are listed together with their origin.
2. **Pick a result** — enter the number of the entry you want.
3. **Pick a language** — the available options depend on the source.
4. **Pick episodes** — single, range, or all.
5. **Download** — files are saved to `Downloads/`.

You can paste a full URL at the search prompt to skip searching.

The language tag reflects the audio track you selected. Downloading the same
item in two languages produces two separate files.

Filenames are sanitized for Windows compatibility and capped at 200
characters to stay under the OS path limit.

## Configuration

Editable constants live in `src/streamforge/config.py`:

- `DOWNLOADS_DIR` — output folder (default: `Downloads/`)
- `LANG_TO_ISO` — language mapping used for audio track selection
- Base URLs and rate limits

DNS-over-HTTPS resolution is enabled by default for domains that are
frequently DNS-blocked. It uses Cloudflare and Google as resolvers, with
automatic fallback. See `src/streamforge/sites/serienstream.py` for the
implementation.

## Project Structure
streamforge/
├── src/
│ └── streamforge/
│ ├── cli.py Interactive entry point
│ ├── config.py Constants and paths
│ ├── download.py yt-dlp wrapper with progress bar
│ ├── filenames.py Filename sanitization
│ ├── models.py Dataclasses
│ ├── resolver.py Site + hoster coordination
│ ├── ui.py Terminal styling and prompts
│ ├── sites/ One file per streaming source
│ │ ├── base.py Site interface
│ │ ├── aniworld.py
│ │ ├── serienstream.py
│ │ └── filmo.py
│ ├── hosters/ One file per stream hoster
│ │ ├── base.py Hoster interface
│ │ ├── byse.py Filemoon / Byse
│ │ └── voe.py VOE
│ └── pow/ Proof-of-work extension (Cython)
│ ├── pow_cython.pyx
│ └── pow_cython.*.pyd
├── setup.py Build script
├── pyproject.toml Package metadata
├── requirements.txt
├── setup.bat First-time setup (Windows)
├── run.bat Start the program (Windows)
└── README.md

## Adding a New Source

Create `src/streamforge/sites/yoursite.py` with a class that inherits from
`Site` and implements three methods:

```python
class YourSite(Site):
    name = "YourSite"
    domains = ("yoursite.tld",)
    languages = (...)
    aliases = {}              # hoster name overrides for this site

    def search(self, query): ...
    def build_episode_list(self, series_url): ...
    def resolve_hoster(self, episode_url, hoster_name, language): ...
Register it in src/streamforge/sites/__init__.py. It will be picked up by
the search loop and the resolver automatically.

Adding a New Hoster
Same pattern in src/streamforge/hosters/. Register in
src/streamforge/hosters/__init__.py. Any site can then reference it by
name (or a site-specific alias).

Troubleshooting
"Python not found" when running setup.bat
Install Python 3.10+ from python.org and check "Add Python to PATH" during
setup.

"pow_cython not loadable"
The prebuilt module targets Python 3.12 on 64-bit Windows. On a different
version, rebuild:

text
pip install cython
python setup.py build_ext --inplace
Downloads are slow
Some hosters throttle single-connection downloads. StreamForge requests 16
parallel connections per file by default. If a file still downloads slowly,
the hoster is limiting you and there is no client-side fix.

A source returns no results
Sources occasionally go offline or change domains. Failures in one source
do not affect the others. Check the source's URL in src/streamforge/config.py
if it keeps returning nothing.

DNS errors on a specific source
Some sources are DNS-blocked on certain ISPs. StreamForge uses DNS-over-HTTPS
via Cloudflare and Google to bypass this automatically. If a source still
fails, run:

text
python -c "import requests; print(requests.get('https://cloudflare-dns.com/dns-query', params={'name': 'example.com', 'type': 'A'}, headers={'Accept': 'application/dns-json'}).json())"
to confirm DoH is reachable from your network.

"Video not found" for a specific episode
The hoster may have removed the file or region-locked it. Try the other
hoster if one is available.

Legal
StreamForge is a downloader. It does not host, index, or distribute any
content. All media is retrieved from the sources configured by the user.
Users are responsible for ensuring their use complies with the terms of
service of those sources and with local copyright law.
