"""Stripping the HN prefix an ingested title may carry."""

from __future__ import annotations

import pytest

from app.features.collect.titles import clean_title


@pytest.mark.parametrize(
    "given, expected",
    [
        ("Show HN: my project", "my project"),
        ("Ask HN: what do you think?", "what do you think?"),
        ("Tell HN: something", "something"),
        ("Launch HN: a startup", "a startup"),
        ("show hn: lowercase works", "lowercase works"),
        ("Beta: djs", "djs"),
        ("Tool: Atuin Threads", "Atuin Threads"),
        ("Devin Apps (3 minute read)", "Devin Apps"),
        ("Ace (Website)", "Ace"),
        ("AlphaEvolve (GitHub Repo)", "AlphaEvolve"),
        ("Tips (and tricks) for agents", "Tips (and tricks) for agents"),
        # no prefix — unchanged
        ("A normal title", "A normal title"),
        # not a prefix, just a mention
        ("Why Show HN posts do well", "Why Show HN posts do well"),
    ],
)
def test_clean_title_strips_hn_prefix_and_newsletter_labels(
    given: str, expected: str
) -> None:
    assert clean_title(given) == expected
