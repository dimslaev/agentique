"""URL normalisation: feed endpoints and comparable hostnames."""

from __future__ import annotations

from urllib.parse import urlparse


def feed_url(url: str, is_substack: bool = False) -> str:
    """Normalise a publisher link to the feed endpoint to actually poll.

    A bare Substack link (``https://foo.substack.com``, or a custom domain
    stored under the ``substack`` platform) serves the HTML site, not the feed -
    feedparser finds no entries and the source silently yields nothing. Substack
    always serves the feed at ``/feed``. Pass ``is_substack`` when the link's
    platform says so; the host check catches bare substack.com links stored
    under ``rss``. Idempotent, so it is safe to apply more than once.
    """
    trimmed = url.rstrip("/")
    if (is_substack or trimmed.endswith(".substack.com")) and not trimmed.endswith(
        "/feed"
    ):
        return f"{trimmed}/feed"
    return url


def hostname(url: str) -> str:
    """Lowercase host without a ``www.`` prefix, or "" if the URL has no host."""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return ""
    return host.lower().removeprefix("www.")
