"""Small shared helpers used across the pipeline.

Deliberately dependency-light so any module can import it without cycles.
LLM-output cleanup lives in ``pipeline.llm_text``; HTTP in
``pipeline.sources.http``.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

WINDOW_HOURS = 168

HN_PREFIX_RE = re.compile(r"^(?:Show|Launch|Ask|Tell) HN:\s*", re.IGNORECASE)


def log(message: str) -> None:
    ts = datetime.now(UTC).isoformat()
    print(f"[{ts}] {message}")


def wait_ms(ms: int) -> None:
    time.sleep(ms / 1000)


def enum_value(raw: Any) -> str:
    """The ``.value`` of an enum-ish object, else the object itself, as a str.

    BAML returns plain strings for some fields and enum members for others, and
    which one it is has changed across regenerations — callers tolerate both
    rather than depend on it.
    """
    return str(getattr(raw, "value", raw))


def clean_title(title: str) -> str:
    """Strip the ``Show HN:`` / ``Ask HN:`` style prefix a title may carry."""
    return HN_PREFIX_RE.sub("", title).strip()


def feed_url(url: str, is_substack: bool = False) -> str:
    """Normalise a publisher link to the feed endpoint to actually poll.

    A bare Substack link (``https://foo.substack.com``, or a custom domain
    stored under the ``substack`` platform) serves the HTML site, not the feed —
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


def parse_date(date_str: str | None) -> datetime | None:
    """Parse an RFC 2822 (RSS ``pubDate``) or ISO 8601 date, or None.

    Feeds emit both formats, so try RFC 2822 first and fall back to ISO —
    ``Z`` suffixes included, which ``fromisoformat`` rejects before 3.11.
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
    """Is this date recent enough to ingest?

    An absent or unparseable date returns True on purpose: dropping an article
    because its feed emitted a date we cannot read loses real content, while
    keeping it only risks a stale item that scoring can still reject.
    """
    if not date_str:
        return True
    published = parse_date(date_str)
    if published is None:
        return True
    try:
        hours_ago = (
            datetime.now(UTC) - published.astimezone(UTC)
        ).total_seconds() / 3600
        return hours_ago <= window_hours
    except Exception:
        return True
