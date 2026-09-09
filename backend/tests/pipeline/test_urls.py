"""Hostname normalisation. `feed_url` is covered in test_feed_content.py."""

from __future__ import annotations

import pytest

from pipeline.urls import hostname


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
