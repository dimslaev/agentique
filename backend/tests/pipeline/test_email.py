"""The IMAP newsletter source's two decisions that are pure functions of text:
which publisher sent an email, and what URL an item actually points at. Wrong
in the first means a real newsletter is silently skipped or a stranger's mail
is attributed to a publisher; wrong in the second means the pipeline stores a
tracking link that dies with the campaign, or stores one post twice.
"""

from __future__ import annotations

import pytest

from pipeline.sources.email import (
    _canonical_url,
    _match_sender,
    _unwrap_tracking_url,
)

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


# ─── tracker unwrapping ──────────────────────────────────────────────────────
# A newsletter links through its own redirector. The destination is what the
# pipeline stores, so recovering it from the wrapper — without a request, when
# the wrapper spells it out — is the whole job of this half of the source.


def test_unwraps_a_percent_encoded_destination():
    assert (
        _unwrap_tracking_url(
            "https://tracking.tldrnewsletter.com/CL0/"
            "https:%2F%2Fexample.com%2Fposts%2Fone/1/0100019a626e0311"
        )
        == "https://example.com/posts/one"
    )


def test_unwraps_a_literal_destination_with_its_own_path_separators():
    assert (
        _unwrap_tracking_url(
            "https://tracking.tldrnewsletter.com/CL0/"
            "https://aws.amazon.com/build/ai-series/1/0100019a626e0311"
        )
        == "https://aws.amazon.com/build/ai-series"
    )


def test_keeps_the_destination_query_while_dropping_the_tracker_tail():
    """The tail is the tracker's message id and click token, appended after the
    destination; the destination's own query must survive it."""
    assert (
        _unwrap_tracking_url(
            "https://tracking.tldrnewsletter.com/CL0/"
            "https:%2F%2Fexample.com%2Fp%3Fid%3D7/1/0100019a626e0311"
        )
        == "https://example.com/p?id=7"
    )


def test_an_opaque_token_cannot_be_unwrapped():
    """Nothing to recover without a request — the caller follows the redirect."""
    assert _unwrap_tracking_url("https://links.tldrnewsletter.com/zPfy8Y") is None


def test_a_direct_link_is_not_a_wrapper():
    assert _unwrap_tracking_url("https://example.com/blog/post") is None


# ─── URL canonicalization ────────────────────────────────────────────────────
# Two links to one post must reduce to one string, or dedup stores it twice.


def test_drops_campaign_params_and_keeps_the_rest():
    assert (
        _canonical_url("https://example.com/p?id=7&utm_source=tldr&page=2")
        == "https://example.com/p?id=7&page=2"
    )


def test_drops_campaign_params_hidden_after_a_fragment():
    """Newsletters append their params after the anchor, where a query parser
    never looks."""
    assert (
        _canonical_url("https://example.com/p/#section?utm_source=tldrai")
        == "https://example.com/p#section"
    )


def test_a_trailing_slash_does_not_make_a_second_url():
    assert _canonical_url("https://example.com/p/") == _canonical_url(
        "https://example.com/p"
    )


def test_the_host_is_lowercased_but_the_path_is_not():
    """Hosts are case-insensitive; paths are not, and lowercasing one would
    404."""
    assert (
        _canonical_url("https://Example.COM/Posts/One")
        == "https://example.com/Posts/One"
    )


def test_a_bare_root_url_keeps_its_slash():
    assert _canonical_url("https://example.com/") == "https://example.com/"
