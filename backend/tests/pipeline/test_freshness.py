"""The freshness window that decides what enters the funnel."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pipeline.freshness import is_within_window, parse_date

# ─── parse_date ──────────────────────────────────────────────────────────────


def test_parses_rfc_2822_as_rss_pubdate_emits_it():
    parsed = parse_date("Wed, 02 Oct 2002 13:00:00 GMT")
    assert parsed is not None
    assert (parsed.year, parsed.month, parsed.day) == (2002, 10, 2)


def test_parses_iso_8601():
    parsed = parse_date("2026-07-17T12:30:00+00:00")
    assert parsed is not None
    assert (parsed.year, parsed.month, parsed.day) == (2026, 7, 17)


def test_parses_iso_with_z_suffix():
    """`Z` is what feeds actually emit; fromisoformat rejected it before 3.11."""
    parsed = parse_date("2026-07-17T12:30:00Z")
    assert parsed is not None
    assert parsed.tzinfo is not None


@pytest.mark.parametrize("given", [None, "", "not a date", "2026-13-45"])
def test_unparseable_dates_return_none_rather_than_raising(given):
    assert parse_date(given) is None


# ─── is_within_window ────────────────────────────────────────────────────────


def test_recent_date_is_within_window():
    recent = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    assert is_within_window(recent) is True


def test_old_date_is_outside_window():
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    assert is_within_window(old) is False


def test_window_boundary_is_inclusive():
    edge = (datetime.now(UTC) - timedelta(hours=10)).isoformat()
    assert is_within_window(edge, window_hours=24) is True
    assert is_within_window(edge, window_hours=1) is False


@pytest.mark.parametrize("given", [None, "", "garbage"])
def test_missing_or_unparseable_date_is_kept_not_dropped(given):
    """Deliberate: dropping an article because its feed emitted a date we cannot
    read loses real content, while keeping it only risks a stale item that
    scoring can still reject."""
    assert is_within_window(given) is True
