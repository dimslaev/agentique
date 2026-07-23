"""Small dependency-light helpers: logging, time, hostnames, feed dates."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

# Feeds emit stale items; anything older than this is ignored at fetch time.
WINDOW_HOURS = 168


def log(message: str) -> None:
    print(f"[{datetime.now(UTC).isoformat()}] {message}")


def wait_ms(ms: int) -> None:
    time.sleep(ms / 1000)


def hostname(url: str) -> str:
    """Lowercase host without a ``www.`` prefix, or "" if the URL has no host."""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return ""
    return host.lower().removeprefix("www.")


def parse_date(date_str: str | None) -> datetime | None:
    """Parse an RFC 2822 (RSS ``pubDate``) or ISO 8601 date, or None.

    Feeds emit both, so try RFC 2822 first and fall back to ISO — ``Z`` suffixes
    included, which ``fromisoformat`` rejects on older interpreters.
    """
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return None


def is_within_window(date_str: str | None, window_hours: int = WINDOW_HOURS) -> bool:
    """Is this feed date recent enough to ingest?

    An absent or unparseable date returns True on purpose: dropping an article
    because its feed emitted a date we cannot read loses real content, while
    keeping it only risks a stale item that scoring can still reject.
    """
    published = parse_date(date_str)
    if published is None:
        return True
    try:
        hours_ago = (datetime.now(UTC) - published.astimezone(UTC)).total_seconds() / 3600
        return hours_ago <= window_hours
    except Exception:
        return True
