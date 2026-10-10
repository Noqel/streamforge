# StreamForge

A command-line downloader for anime, series, and movies from three German streaming sites.

## Overview

StreamForge searches three sources, resolves the hoster links, and downloads the
streams as MP4 files. It handles the extractor logic, proof-of-work captchas, and
multi-audio track selection for each source.

Supported sources:

| Source         | Content                        | Languages                          |
|----------------|--------------------------------|------------------------------------|
| aniworld.to    | Anime                          | German Dub, German Sub, Japanese Sub |
| serienstream.to| Series and movies              | German, English                    |
| filmo.to       | Movies                         | German, English                    |

## Requirements

- **Python 3.10 or newer** (3.12 recommended)
- **Windows 10/11** for the prebuilt package. Linux and macOS work from source.
- An internet connection

No C compiler, Nim toolchain, or build tools are required. The proof-of-work
extension ships precompiled for Windows 64-bit with Python 3.12.

## Installation

### Windows (prebuilt package)

1. Download and extract the release ZIP.
2. Double-click `setup.bat`. This creates a virtual environment and installs
   all Python dependencies. It takes about 30 seconds.
3. Double-click `run.bat` to start the program.

### From source (any platform)
python -m venv venv
venv/Scripts/activate # Windows
source venv/bin/activate # Linux / macOS
pip install -r requirements.txt
pip install cython
python setup.py build_ext --inplace
python src/main.py

text

The `setup.py build_ext` step compiles the Cython proof-of-work module for
your platform. It needs a C compiler (gcc, clang, or MSVC Build Tools).

## Usage

Run `run.bat` (Windows) or `python src/main.py` (other platforms). The program
walks you through each step:

1. **Search** — type a series or movie name. All three sources are queried in
   parallel and the results are listed together with their origin.
2. **Pick a result** — enter the number of the entry you want.
3. **Pick a language** — the options depend on the source:
   - AniWorld: German Dub, German Sub, Japanese Sub
   - SerienStream and Filmo: German, English
4. **Pick episodes** — for series, choose a single episode, a range, or
   everything.
5. **Download** — files are saved to the `Downloads/` folder next to the script.

You can also paste a full URL at the search prompt to skip the search step.

## Output

Files are named as follows:
Downloads/
├── Demon Slayer Kimetsu No Yaiba S01E01 [GER-DUB].mp4
├── Demon Slayer Kimetsu No Yaiba S01E02 [GER-DUB].mp4
└── Fight Club [ENG-SUB].mp4

text

The language tag in brackets reflects the audio track you selected. Downloading
the same item in two languages produces two separate files.

## Configuration

Editable constants live in `src/config.py`:

- `DOWNLOADS_DIR` — output folder (default: `Downloads/`)
- `_LANG_TO_ISO` — language mapping used for audio track selection
- Base URLs for each source

## Project structure
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
Install Python 3.10 or newer from python.org and check "Add Python to PATH"
during installation.

**"pow_cython not loadable"**
The prebuilt module is for Python 3.12 on 64-bit Windows. If you use a
different version, build it yourself:
pip install cython
python build/setup.py build_ext --inplace
copy build/pow_cython*.pyd src/pow/

text

**Downloads are slow**
Some hosters throttle single-connection downloads. The program requests 16
parallel connections per file by default. If a file still downloads slowly,
the hoster is limiting you and there is no client-side fix.

**A source returns no results**
Sources occasionally go offline or change their domain. Failures in one source
do not affect the others. If a source keeps returning no results, check that
its URL in `src/config.py` is still correct.

**"Video not found" for a specific episode**
The hoster may have removed that file, or it may be region-locked. Try the same
episode with the other hoster if one is available.

## Legal

StreamForge is a downloader. It does not host any content. All streams are
retrieved from the sources listed above. Users are responsible for ensuring
their use complies with the terms of service of those sources and with local
copyright law.
