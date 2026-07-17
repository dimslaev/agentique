"""Shared helpers. Each of these was duplicated 2-5x before being centralised,
so a behaviour change here now reaches every caller at once.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

import pytest

from pipeline.utils import (
    clean_title,
    enum_value,
    hostname,
    is_within_window,
    parse_date,
)

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


# ─── hostname ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://github.com/foo/bar", "github.com"),
        ("https://www.github.com/foo", "github.com"),
        ("https://GitHub.COM/foo", "github.com"),
        ("https://sub.example.co.uk/x?y=1", "sub.example.co.uk"),
        # only a leading www. goes — not any subdomain
        ("https://www2.example.com", "www2.example.com"),
    ],
)
def test_hostname_normalises(url, expected):
    assert hostname(url) == expected


@pytest.mark.parametrize("given", ["", "not a url", "mailto:x@y.com"])
def test_hostname_returns_empty_when_there_is_no_host(given):
    assert hostname(given) == ""


# ─── enum_value ──────────────────────────────────────────────────────────────


class _Colour(StrEnum):
    red = "red"


def test_enum_value_unwraps_an_enum():
    assert enum_value(_Colour.red) == "red"


def test_enum_value_passes_a_plain_string_through():
    """BAML returns plain strings for some fields and enum members for others,
    and which one has changed across regenerations."""
    assert enum_value("red") == "red"


# ─── clean_title ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "given, expected",
    [
        ("Show HN: my project", "my project"),
        ("Ask HN: what do you think?", "what do you think?"),
        ("Tell HN: something", "something"),
        ("Launch HN: a startup", "a startup"),
        ("show hn: lowercase works", "lowercase works"),
        # no prefix — unchanged
        ("A normal title", "A normal title"),
        # not a prefix, just a mention
        ("Why Show HN posts do well", "Why Show HN posts do well"),
    ],
)
def test_clean_title_strips_only_a_leading_hn_prefix(given, expected):
    assert clean_title(given) == expected
