"""Timezone-aware clock helpers shared by every domain's models."""

from __future__ import annotations

from datetime import UTC, datetime


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)
