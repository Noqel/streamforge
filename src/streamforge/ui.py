# src/streamforge/ui.py
import time

from rich.align import Align
from rich.console import Console
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme


# ---------------------------------------------------------------
# Theme
# ---------------------------------------------------------------
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


# ---------------------------------------------------------------
# Banner
# ---------------------------------------------------------------
BANNER = r"""
  ███████╗████████╗██████╗ ███████╗ █████╗ ███╗   ███╗███████╗ ██████╗ ██████╗  ██████╗ ███████╗
  ██╔════╝╚══██╔══╝██╔══██╗██╔════╝██╔══██╗████╗ ████║██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
  ███████╗   ██║   ██████╔╝█████╗  ███████║██╔████╔██║█████╗  ██║   ██║██████╔╝██║  ███╗█████╗
  ╚════██║   ██║   ██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝
  ███████║   ██║   ██║  ██║███████╗██║  ██║██║ ╚═╝ ██║██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
  ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝
"""


def show_banner():
    from .config import VERSION
    console.print(BANNER, style="bold bright_green", highlight=False)
    console.print(Align.center(
        Text(">> multi-source stream downloader  ·  aniworld · serienstream · filmo",
             style="bold green")
    ))
    console.print(Align.center(
        Text(f"version {VERSION}  ·  session secured  ·  ready",
             style="dim green")
    ))
    console.print()


def boot_sequence():
    """Small fake boot log — call once at startup."""
    steps = [
        ("initializing core",   "requests · bs4 · yt-dlp · rich"),
        ("loading sources",     "aniworld.to · serienstream.to · filmo.to"),
        ("loading hosters",     "filemoon · byse · voe"),
        ("dns resolver",        "doh (cloudflare / google)"),
        ("pow engine",          "numba-free · cython native"),
        ("output directory",    "Downloads/"),
    ]
    console.print("[dim green]  [ boot ] initializing...[/]")
    for label, detail in steps:
        console.print(f"[dim green]  [ ok  ][/] [green]{label:<20}[/] [dim]{detail}[/]")
        time.sleep(0.08)
    console.print()


# ---------------------------------------------------------------
# Status messages
# ---------------------------------------------------------------
def info(msg):  console.print(f"[bold bright_green][*][/] {msg}")
def ok(msg):    console.print(f"[bold green][+][/] {msg}")
def warn(msg):  console.print(f"[bold yellow][!][/] {msg}")
def err(msg):   console.print(f"[bold red][x][/] {msg}")


# ---------------------------------------------------------------
# Section headers
# ---------------------------------------------------------------
def section(title):
    console.print()
    console.print(Rule(
        f"[bold bright_green][ {title.upper()} ][/]",
        style="bright_green",
    ))
    console.print()


# ---------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------
PROMPT = "[bold bright_green]$[/]"


def ask(question, default=None):
    """Standard prompt with the hacker '$' symbol."""
    return Prompt.ask(f"{PROMPT} {question}", default=default).strip()


def ask_int(question):
    from rich.prompt import IntPrompt
    return IntPrompt.ask(f"{PROMPT} {question}")


def confirm(question, default=True):
    from rich.prompt import Confirm
    return Confirm.ask(f"{PROMPT} {question}", default=default)


def pause():
    console.print()
    Prompt.ask("[dim green]press Enter to continue[/]",
               default="", show_default=False)


# ---------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------
def hacker_table(**kwargs):
    """Return a Table pre-styled in the hacker look."""
    from rich import box
    defaults = dict(
        box=box.SIMPLE_HEAVY,
        border_style="bright_green",
        header_style="bold bright_green",
        padding=(0, 1),
    )
    defaults.update(kwargs)
    return Table(**defaults)