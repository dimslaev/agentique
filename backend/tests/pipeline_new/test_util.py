"""Dependency-light helpers: feed dates, freshness window, hostnames."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pipeline_new.util import hostname, is_within_window, parse_date


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.therundown.ai/p/x", "therundown.ai"),
        ("https://openai.com/blog/y", "openai.com"),
        ("http://EXAMPLE.com/Z", "example.com"),
        ("not a url", ""),
    ],
)
def test_hostname(url: str, expected: str) -> None:
    assert hostname(url) == expected


def test_parse_date_rfc2822() -> None:
    d = parse_date("Wed, 22 Jul 2026 09:00:00 +0000")
    assert d is not None and d.year == 2026 and d.month == 7 and d.day == 22


def test_parse_date_iso_with_z() -> None:
    d = parse_date("2026-07-22T09:00:00Z")
    assert d is not None and d.hour == 9


@pytest.mark.parametrize("bad", [None, "", "not a date"])
def test_parse_date_bad(bad: str | None) -> None:
    assert parse_date(bad) is None


def test_within_window_recent() -> None:
    recent = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert is_within_window(recent) is True


def test_outside_window_old() -> None:
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    assert is_within_window(old) is False


@pytest.mark.parametrize("val", [None, "", "garbage-date"])
def test_window_keeps_unparseable(val: str | None) -> None:
    """An unreadable date must not drop the article — keep and let scoring judge."""
    assert is_within_window(val) is True
