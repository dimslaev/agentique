"""Timezone-aware clock helpers, and parsing the dates feeds emit."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


def parse_date(date_str: str | None) -> datetime | None:
    """Parse an RFC 2822 (RSS ``pubDate``) or ISO 8601 date, or None.

    Feeds emit both formats, so try RFC 2822 first and fall back to ISO -
    ``Z`` suffixes included, which ``fromisoformat`` rejects before 3.11. A date
    with no offset (or RFC 2822's ``-0000``) is read as UTC, so the result never
    depends on the server's local timezone.
    """
    if not date_str:
        return None
    try:
        parsed = parsedate_to_datetime(date_str)
    except Exception:
        try:
            parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
