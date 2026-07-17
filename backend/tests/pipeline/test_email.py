"""Sender matching for the IMAP newsletter source: which configured publisher,
if any, sent this email. Wrong here means either a real newsletter is silently
skipped, or an unrelated inbox message gets attributed to a publisher.
"""

from __future__ import annotations

import pytest

from pipeline.sources.email import _match_sender

SOURCES = [
    ("@substack.com", "Some Substack"),
    ("news@bensbites.com", "Ben's Bites"),
]


def test_at_prefix_matches_any_local_part_at_that_exact_domain():
    assert _match_sender("writer@substack.com", SOURCES) == "Some Substack"


def test_at_prefix_does_not_match_a_deeper_subdomain():
    """ "@substack.com" matches "anyone@substack.com" only — the check is a
    string suffix on the whole address, so a subdomain like "foo.substack.com"
    changes what precedes "substack.com" and no longer ends in "@substack.com"."""
    assert _match_sender("writer@foo.substack.com", SOURCES) is None


@pytest.mark.parametrize(
    "address",
    ["writer@notsubstack.com", "writer@evilsubstack.com"],
)
def test_at_prefix_does_not_match_a_lookalike_domain(address):
    """Confirms the check is a suffix match requiring the literal "@" right
    before the domain, not a raw substring search for "substack.com"."""
    assert _match_sender(address, SOURCES) is None


def test_exact_pattern_requires_an_exact_address_match():
    assert _match_sender("news@bensbites.com", SOURCES) == "Ben's Bites"


def test_exact_pattern_does_not_match_a_different_local_part_at_the_same_domain():
    assert _match_sender("other@bensbites.com", SOURCES) is None


def test_matching_is_case_insensitive():
    assert _match_sender("Writer@Substack.COM", SOURCES) == "Some Substack"


def test_no_match_returns_none():
    assert _match_sender("someone@example.com", SOURCES) is None


def test_empty_sources_never_matches():
    assert _match_sender("writer@substack.com", []) is None
