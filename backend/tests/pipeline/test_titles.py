"""Stripping the HN prefix an ingested title may carry."""

from __future__ import annotations

import pytest

from pipeline.titles import clean_title


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
