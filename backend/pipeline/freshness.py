"""How recent an item has to be to enter the funnel."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.dates import parse_date

WINDOW_HOURS = 48


def is_within_window(date_str: str | None, window_hours: int = WINDOW_HOURS) -> bool:
    """Is this date recent enough to ingest?

    An absent or unparsable date returns True on purpose: dropping an article
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
