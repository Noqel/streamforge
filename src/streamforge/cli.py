# src/streamforge/cli.py
from rich.align import Align
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.rule import Rule
from rich.table import Table
from rich import box
from rich.text import Text

# cli.py — Imports oben
from .ui import (
    console, show_banner, boot_sequence,
    info, ok, warn, err, section, pause,
    ask, ask_int, confirm, hacker_table, PROMPT,
)
from .config import VERSION
from .sites import ALL_SITES
from .download import run_downloads


def _pick_series():
    console.print("[bold]What do you want to download?[/]")
    console.print("[dim]Type a name to search, or paste a full URL.[/]\n")

    query = ask("")                            # ← statt Prompt.ask(...)
    if not query:
        return None, None
    if query.startswith(("http://", "https://")):
        return query, None

    combined = []
    with console.status(f"[bright_green]searching for '{query}'...[/]",
                        spinner="dots12"):
        for site in ALL_SITES:
            try:
                hits = site.search(query)
                for h in hits:
                    h.source = site.name
                console.print(f"  [dim green][*][/] [green]{site.name:<14}[/] "
                              f"[dim]{len(hits)} hit(s)[/]")
                combined.extend(hits)
            except Exception as e:
                console.print(f"  [dim green][x][/] [green]{site.name:<14}[/] "
                              f"[yellow]{e}[/]")

    if not combined:
        warn(f"No results for '{query}'.")
        return None, None

    table = hacker_table()
    table.add_column("#",      style="bold yellow", justify="right", width=4)
    table.add_column("Title",  style="bold white")
    table.add_column("Source", style="bright_green", width=14)

    for i, r in enumerate(combined, 1):
        table.add_row(str(i), r.title, r.source)

    console.print()
    console.print(table)
    console.print()

    while True:
        choice = ask(f"select [bold](1-{len(combined)})[/] or 'q' to quit")
        if choice.lower() in ("q", "quit", "exit"):
            return None, None
        try:
            idx = int(choice)
            if 1 <= idx <= len(combined):
                r = combined[idx - 1]
                return r.url, r.title
        except ValueError:
            pass
        warn("Invalid choice.")


def _pick_language(site):
    table = hacker_table()
    table.add_column("#",         style="bold yellow", justify="right", width=4)
    table.add_column("Language",  style="bold white")
    table.add_column("Info",      style="dim")

    for i, lang in enumerate(site.languages, 1):
        suffix = "  [dim](default)[/]" if i == 1 else ""
        table.add_row(str(i), f"{lang.label}{suffix}", lang.hint)

    console.print()
    console.print(table)
    console.print()

    while True:
        choice = ask(f"pick language [bold](1-{len(site.languages)})[/]",
                     default="1")
        try:
            idx = int(choice)
            if 1 <= idx <= len(site.languages):
                return site.languages[idx - 1].code
        except ValueError:
            pass
        warn("Invalid choice.")


def _display_episodes(items):
    table = hacker_table()
    table.add_column("#",     style="bold yellow", justify="right", width=5)
    table.add_column("S / E", style="magenta", width=10)
    table.add_column("Title", style="white")

    for i, item in enumerate(items, 1):
        if item.type == "episode":
            s = f"S{item.season:02d}" if item.season else "S??"
            e = f"E{item.episode:02d}" if item.episode else "E??"
            tag = f"{s} {e}"
        else:
            tag = "[yellow]MOVIE[/]"
        table.add_row(str(i), tag, item.title or "—")

    console.print(table)


def _pick_items(items):
    console.print("\n[bold]What to download?[/]")
    console.print("  [bright_green]1[/]  Single item")
    console.print("  [bright_green]2[/]  Everything")
    console.print("  [bright_green]3[/]  Range\n")

    while True:
        choice = ask("")
        if choice == "1":
            n = ask_int(f"item number (1-{len(items)})")
            if 1 <= n <= len(items):
                return [items[n - 1]]
        elif choice == "2":
            return items
        elif choice == "3":
            rng = ask("range [dim](e.g. 1-5)[/]")
            try:
                a, b = map(int, rng.split("-"))
                if 1 <= a <= b <= len(items):
                    return items[a - 1:b]
            except Exception:
                pass
        warn("Invalid choice.")


def main():
    from .sites import find_site

    console.clear()
    show_banner()
    boot_sequence()

    while True:
        try:
            series_url, series_title = _pick_series()
            if not series_url:
                break

            site = find_site(series_url)
            if not site:
                err(f"no site for {series_url}")
                pause()
                continue

            if series_title:
                ok(f"selected: [bold]{series_title}[/]")

            section("language")
            language = _pick_language(site)
            ok(f"language: [bold]{language}[/]")

            section("episodes")
            with console.status("[bright_green]fetching episodes...[/]",
                                spinner="dots12"):
                items = site.build_episode_list(series_url)

            if not items:
                warn("nothing found.")
                pause()
                continue

            ok(f"found [bold]{len(items)}[/] items")
            _display_episodes(items)

            if len(items) == 1:
                selected = items
                info("single item — auto-selected.")
            else:
                selected = _pick_items(items)

            run_downloads(selected, series_url, language)

        except KeyboardInterrupt:
            console.print()
            warn("cancelled.")
            break
        except Exception as e:
            console.print()
            err(str(e))
            pause()
            continue

        console.print()
        if not confirm("another download?", default=True):
            break

    console.print()
    console.print(Rule(style="bright_green"))
    console.print(Align.center(Text("session terminated",
                                    style="bold bright_green")))
    console.print()