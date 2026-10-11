# src/streamforge/resolver.py
from .sites import find_site
from .hosters import find_hoster, hoster_order_for
from .ui import info, warn, err


def get_stream_url(episode_url, language):
    site = find_site(episode_url)
    if not site:
        raise RuntimeError(f"No site handles {episode_url}")

    for display_name in hoster_order_for(site):
        info(f"Trying [bold]{display_name}[/] ({language})...")
        try:
            # Find the canonical hoster for this display name
            hoster = find_hoster(display_name)
            if hoster is None:
                continue

            redirect = site.resolve_hoster(episode_url, display_name, language)
            if not redirect:
                warn(f"{display_name} not available.")
                continue

            return hoster.extract(redirect)
        except Exception as e:
            err(f"{display_name}: {e}")

    raise RuntimeError("No working stream found.")