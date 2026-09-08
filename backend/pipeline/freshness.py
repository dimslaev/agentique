"""How recent an item has to be to enter the funnel."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

WINDOW_HOURS = 48


def parse_date(date_str: str | None) -> datetime | None:
    """Parse an RFC 2822 (RSS ``pubDate``) or ISO 8601 date, or None.

    Feeds emit both formats, so try RFC 2822 first and fall back to ISO -
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
