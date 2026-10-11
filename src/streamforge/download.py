# src/streamforge/download.py
import time
from pathlib import Path
from urllib.parse import unquote

import yt_dlp
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    DownloadColumn, TimeRemainingColumn,
)

from .ui import console, section, info, ok, warn, err
from .config import DOWNLOADS_DIR, LANG_TO_ISO
from .filenames import build_filename


def _ensure_downloads_dir():
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _fmt_speed(bps):
    if not bps or bps <= 0:
        return ""
    if bps >= 1024 * 1024:
        return f"{bps / 1024 / 1024:6.2f} MiB/s"
    return f"{bps / 1024:6.0f} KiB/s"


def _fmt_eta(seconds):
    if seconds is None or seconds < 0:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def download_hls(stream_url, output_filename, audio_lang=None):
    if "|" in stream_url:
        url_part, header_part = stream_url.split("|", 1)
        headers = {}
        for item in header_part.split("&"):
            if "=" in item:
                k, v = item.split("=", 1)
                headers[k.strip()] = unquote(v)
    else:
        url_part, headers = stream_url, {}

    if audio_lang:
        fmt = (
            f"bestvideo+bestaudio[language={audio_lang}]"
            f"/bestvideo+bestaudio/best"
        )
    else:
        fmt = "bestvideo+bestaudio/best"

    short = output_filename if len(output_filename) <= 55 else output_filename[:52] + "..."

    progress = Progress(
        SpinnerColumn(style="bright_green"),
        TextColumn("[bold bright_green]{task.description}"),
        BarColumn(bar_width=None,
                  complete_style="bright_green",
                  finished_style="green"),
        DownloadColumn(),
        TextColumn("[bright_green]{task.fields[speed_text]:>12}[/]"),
        TextColumn("[green]{task.fields[eta_text]:>10}[/]"),
        console=console,
    )

    with progress:
        # IMPORTANT: declare the custom fields here, otherwise
        # {task.fields[speed_text]} raises a KeyError.
        task = progress.add_task(
            short,
            total=None,
            speed_text="",
            eta_text="",
        )

        def hook(d):
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                done = d.get("downloaded_bytes") or 0
                speed = d.get("speed")
                eta = d.get("eta")

                kw = {
                    "completed":  done,
                    "speed_text": _fmt_speed(speed),
                    "eta_text":   _fmt_eta(eta),
                }
                if total:
                    kw["total"] = total
                progress.update(task, **kw)

            elif status == "finished":
                progress.update(
                    task,
                    description=f"[green]{short}[/]",
                    speed_text="[green]done[/]",
                    eta_text="",
                )

        ydl_opts = {
            "outtmpl": output_filename,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "http_headers": headers,
            "format": fmt,
            "merge_output_format": "mp4",
            "progress_hooks": [hook],
            "concurrent_fragment_downloads": 16,
            "http_chunk_size": 10485760,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_part])


def run_downloads(selected, series_url, language):
    section("Downloads")
    _ensure_downloads_dir()

    total = len(selected)
    success = failed = 0
    audio_iso = LANG_TO_ISO.get(language)

    for i, item in enumerate(selected, 1):
        base_name = build_filename(item, series_url)
        filename = f"{base_name} [{language}]"
        output = DOWNLOADS_DIR / f"{filename}.mp4"

        console.print()
        console.print(f"[bold bright_green]({i}/{total})[/] [bold]{filename}[/]")
        console.print(f"     [dim green]{item.url}[/]")

        try:
            from .resolver import get_stream_url
            stream = get_stream_url(item.url, language)
            download_hls(stream, str(output), audio_lang=audio_iso)
            ok(f"Saved: [bold]{output}[/]")
            success += 1
        except Exception as e:
            err(f"Failed: {e}")
            failed += 1

        if i < total:
            time.sleep(5)

    section("Summary")
    console.print(f"  [bold green][+][/] {success} downloaded")
    if failed:
        console.print(f"  [bold red][x][/] {failed} failed")