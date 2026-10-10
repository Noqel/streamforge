# StreamForge

Downloader for anime, series, and movies from aniworld.to, serienstream.to, and filmo.to.

## Quick Start

**Windows**

1. Extract the ZIP.
2. Double-click `setup.bat` (installs everything, ~30 seconds).
3. Double-click `run.bat`.

**Other platforms**
pip install -r requirements.txt
pip install cython
python setup.py build_ext --inplace
python src/main.py

text

Then follow the prompts: search, pick a result, pick a language, pick episodes.

## Overview

StreamForge searches three sources, resolves the hoster links, and downloads the
streams as MP4 files. It handles extractor logic, proof-of-work captchas, and
multi-audio track selection for each source.

| Source          | Content           | Languages                            |
|-----------------|-------------------|--------------------------------------|
| aniworld.to     | Anime             | German Dub, German Sub, Japanese Sub |
| serienstream.to | Series and movies | German, English                      |
| filmo.to        | Movies            | German, English                      |

## Requirements

- Python 3.10 or newer (3.12 recommended)
- Windows 10/11 for the prebuilt package. Linux and macOS work from source.
- Internet connection

No C compiler, Nim toolchain, or build tools required. The proof-of-work
extension ships precompiled for Windows 64-bit with Python 3.12.

## Usage

Run `run.bat` (Windows) or `python src/main.py` (other platforms). The program
walks you through each step:

1. **Search** — type a series or movie name. All three sources are queried and
   results are listed together with their origin.
2. **Pick a result** — enter the number of the entry you want.
3. **Pick a language** — options depend on the source (see table above).
4. **Pick episodes** — single, range, or all.
5. **Download** — files are saved to `Downloads/`.

You can paste a full URL at the search prompt to skip searching.

## Output
Downloads/
├── Demon Slayer Kimetsu No Yaiba S01E01 [GER-DUB].mp4
├── Demon Slayer Kimetsu No Yaiba S01E02 [GER-DUB].mp4
└── Fight Club [ENG-SUB].mp4

text

The language tag reflects the audio track you selected. Same item in two
languages produces two separate files.

## Configuration

Editable constants live in `src/config.py`:

- `DOWNLOADS_DIR` — output folder (default: `Downloads/`)
- `_LANG_TO_ISO` — language mapping for audio track selection
- Base URLs for each source

## Project Structure
streamforge/
├── src/
│ ├── main.py CLI entry point
│ ├── extractors/ Hoster-specific stream resolvers
│ │ ├── byse.py Filemoon / Byse resolver
│ │ └── voe.py VOE resolver
│ └── pow/ Proof-of-work module (Cython)
│ ├── pow_cython.pyx Source
│ └── pow_cython.*.pyd Compiled binary
├── build/ Build scripts (development only)
├── setup.bat First-time setup (Windows)
├── run.bat Start the program (Windows)
└── requirements.txt

text

## Troubleshooting

**"Python not found" when running setup.bat**
Install Python 3.10+ from python.org and check "Add Python to PATH" during setup.

**"pow_cython not loadable"**
The prebuilt module targets Python 3.12 on 64-bit Windows. On a different
version, rebuild:
pip install cython
python build/setup.py build_ext --inplace
copy build/pow_cython*.pyd src/pow/

text

**Downloads are slow**
Some hosters throttle single-connection downloads. StreamForge requests 16
parallel connections per file. If a file still downloads slowly, the hoster
is limiting you and there is no client-side fix.

**A source returns no results**
Sources occasionally go offline or change domains. Failures in one source do
not affect the others. If a source keeps returning no results, check its URL
in `src/config.py`.

**"Video not found" for a specific episode**
The hoster may have removed the file, or it may be region-locked. Try the
other hoster if one is available.

## Legal

StreamForge is a downloader. It does not host any content. Streams are
retrieved from the sources listed above. Users are responsible for ensuring
their use complies with the terms of service of those sources and with local
copyright law.
