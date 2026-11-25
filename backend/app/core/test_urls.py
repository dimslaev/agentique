"""Hostname and canonical URL normalisation. `feed_url` is covered in
test_feed_content.py."""

from __future__ import annotations

import pytest

from app.core.urls import canonical_url, hostname


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
def test_hostname_normalises(url: str, expected: str) -> None:
    assert hostname(url) == expected


@pytest.mark.parametrize("given", ["", "not a url", "mailto:x@y.com"])
def test_hostname_returns_empty_when_there_is_no_host(given: str) -> None:
    assert hostname(given) == ""


# ─── URL canonicalization ────────────────────────────────────────────────────
# Two links to one post must reduce to one string, or dedup stores it twice.


def test_drops_campaign_params_and_keeps_the_rest() -> None:
    assert (
        canonical_url("https://example.com/p?id=7&utm_source=tldr&page=2")
        == "https://example.com/p?id=7&page=2"
    )


def test_drops_campaign_params_hidden_after_a_fragment() -> None:
    """Newsletters append their params after the anchor, where a query parser
    never looks."""
    assert (
        canonical_url("https://example.com/p/#section?utm_source=tldrai")
        == "https://example.com/p#section"
    )


def test_a_trailing_slash_does_not_make_a_second_url() -> None:
    assert canonical_url("https://example.com/p/") == canonical_url(
        "https://example.com/p"
    )


def test_the_host_is_lowercased_but_the_path_is_not() -> None:
    """Hosts are case-insensitive; paths are not, and lowercasing one would
    404."""
    assert (
        canonical_url("https://Example.COM/Posts/One")
        == "https://example.com/Posts/One"
    )


def test_a_bare_root_url_keeps_its_slash() -> None:
    assert canonical_url("https://example.com/") == "https://example.com/"
