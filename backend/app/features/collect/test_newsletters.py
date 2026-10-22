"""The IMAP newsletter source.

Sender matching and URL unwrapping: which publisher sent an email, and what
URL an item actually points at. Wrong in the first means a real newsletter is
silently skipped or a stranger's mail is attributed to a publisher; wrong in the
second means the pipeline stores a tracking link that dies with the campaign, or
stores one post twice.

Link extraction, rule prefilter and the Jev verdict: what counts as a link and
what text surrounds it, which links are plumbing by rule, and where the
classification thresholds cut. The thresholds were measured on two real issues;
the verdict table is their specification.
"""

from __future__ import annotations

import pytest

from app.core import jev
from app.features.collect import newsletters
from app.features.collect.newsletters import (
    Item,
    Link,
    NewsletterItemKind,
    _canonical_url,
    _match_sender,
    _unwrap_tracking_url,
    extract,
    prefilter,
    verdict,
)

SOURCES = [
    ("@substack.com", "Some Substack"),
    ("news@bensbites.com", "Ben's Bites"),
]


def test_at_prefix_matches_any_local_part_at_that_exact_domain() -> None:
    assert _match_sender("writer@substack.com", SOURCES) == "Some Substack"


def test_at_prefix_does_not_match_a_deeper_subdomain() -> None:
    """ "@substack.com" matches "anyone@substack.com" only — the check is a
    string suffix on the whole address, so a subdomain like "foo.substack.com"
    changes what precedes "substack.com" and no longer ends in "@substack.com"."""
    assert _match_sender("writer@foo.substack.com", SOURCES) is None


@pytest.mark.parametrize(
    "address",
    ["writer@notsubstack.com", "writer@evilsubstack.com"],
)
def test_at_prefix_does_not_match_a_lookalike_domain(address: str) -> None:
    """Confirms the check is a suffix match requiring the literal "@" right
    before the domain, not a raw substring search for "substack.com"."""
    assert _match_sender(address, SOURCES) is None


def test_exact_pattern_requires_an_exact_address_match() -> None:
    assert _match_sender("news@bensbites.com", SOURCES) == "Ben's Bites"


def test_exact_pattern_does_not_match_a_different_local_part_at_the_same_domain() -> (
    None
):
    assert _match_sender("other@bensbites.com", SOURCES) is None


def test_matching_is_case_insensitive() -> None:
    assert _match_sender("Writer@Substack.COM", SOURCES) == "Some Substack"


def test_no_match_returns_none() -> None:
    assert _match_sender("someone@example.com", SOURCES) is None


def test_empty_sources_never_matches() -> None:
    assert _match_sender("writer@substack.com", []) is None


# ─── tracker unwrapping ──────────────────────────────────────────────────────
# A newsletter links through its own redirector. The destination is what the
# pipeline stores, so recovering it from the wrapper — without a request, when
# the wrapper spells it out — is the whole job of this half of the source.


def test_unwraps_a_percent_encoded_destination() -> None:
    assert (
        _unwrap_tracking_url(
            "https://tracking.tldrnewsletter.com/CL0/"
            "https:%2F%2Fexample.com%2Fposts%2Fone/1/0100019a626e0311"
        )
        == "https://example.com/posts/one"
    )


def test_unwraps_a_literal_destination_with_its_own_path_separators() -> None:
    assert (
        _unwrap_tracking_url(
            "https://tracking.tldrnewsletter.com/CL0/"
            "https://aws.amazon.com/build/ai-series/1/0100019a626e0311"
        )
        == "https://aws.amazon.com/build/ai-series"
    )


def test_keeps_the_destination_query_while_dropping_the_tracker_tail() -> None:
    """The tail is the tracker's message id and click token, appended after the
    destination; the destination's own query must survive it."""
    assert (
        _unwrap_tracking_url(
            "https://tracking.tldrnewsletter.com/CL0/"
            "https:%2F%2Fexample.com%2Fp%3Fid%3D7/1/0100019a626e0311"
        )
        == "https://example.com/p?id=7"
    )


def test_an_opaque_token_cannot_be_unwrapped() -> None:
    """Nothing to recover without a request — the caller follows the redirect."""
    assert _unwrap_tracking_url("https://links.tldrnewsletter.com/zPfy8Y") is None


def test_a_direct_link_is_not_a_wrapper() -> None:
    assert _unwrap_tracking_url("https://example.com/blog/post") is None


# ─── URL canonicalization ────────────────────────────────────────────────────
# Two links to one post must reduce to one string, or dedup stores it twice.


def test_drops_campaign_params_and_keeps_the_rest() -> None:
    assert (
        _canonical_url("https://example.com/p?id=7&utm_source=tldr&page=2")
        == "https://example.com/p?id=7&page=2"
    )


def test_drops_campaign_params_hidden_after_a_fragment() -> None:
    """Newsletters append their params after the anchor, where a query parser
    never looks."""
    assert (
        _canonical_url("https://example.com/p/#section?utm_source=tldrai")
        == "https://example.com/p#section"
    )


def test_a_trailing_slash_does_not_make_a_second_url() -> None:
    assert _canonical_url("https://example.com/p/") == _canonical_url(
        "https://example.com/p"
    )


def test_the_host_is_lowercased_but_the_path_is_not() -> None:
    """Hosts are case-insensitive; paths are not, and lowercasing one would
    404."""
    assert (
        _canonical_url("https://Example.COM/Posts/One")
        == "https://example.com/Posts/One"
    )


def test_a_bare_root_url_keeps_its_slash() -> None:
    assert _canonical_url("https://example.com/") == "https://example.com/"


# ─── resolving a product by search ───────────────────────────────────────────


def _product() -> Item:
    return {
        "kind": NewsletterItemKind.Product,
        "name": "Acme SDK",
        "description": "An SDK for agents.",
        "url": "https://www.example-writeup.com/acme",
        "first_party": False,
        "email_date": "2026-09-23T07:00:00+00:00",
        "newsletter_name": "TLDR AI",
    }


def _stub_search(monkeypatch: pytest.MonkeyPatch, pick: str) -> None:
    """Search returns two results; Jev answers ``pick`` from what it is shown."""
    results: list[dict[str, str | None]] = [
        {
            "title": "Acme SDK",
            "url": "https://acme.dev/sdk/",
            "description": "Acme's agent SDK.",
            "published_date": None,
        },
        {
            "title": "Acme on X",
            "url": "https://x.com/acme/status/1",
            "description": "denied",
            "published_date": None,
        },
    ]
    monkeypatch.setattr(newsletters, "tavily_search", lambda query: results)
    monkeypatch.setattr(
        jev, "ask", lambda state, questions: jev.Reply(answers={"link": pick}, cost=0.0)
    )


def test_a_product_resolves_to_the_result_picked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_search(monkeypatch, "1")
    item = newsletters._resolve_product(_product())
    assert item is not None
    assert item["url"] == "https://acme.dev/sdk"
    assert item["source"] == "TLDR AI"


@pytest.mark.parametrize("pick", ["none", "0", "2", "9", "first"])
def test_no_pick_or_a_pick_past_the_list_drops_the_product(
    monkeypatch: pytest.MonkeyPatch, pick: str
) -> None:
    """Jev never sees the denied x.com result, so it picks from a list of one.
    Any other answer is no pick. An unchecked index once raised IndexError,
    which ended the whole night's newsletter source."""
    _stub_search(monkeypatch, pick)
    assert newsletters._resolve_product(_product()) is None


# --- link extraction, prefilter and verdict ---

ZW = "​‌‍﻿­" * 200

FIXTURE = f"""
<html><head><style>.a {{ color: red }}</style></head><body>
<div style="display:none">Today's issue&zwnj;&#8203;{ZW}</div>
<table><tr><td>
  <a href="https://tracking.tldrnewsletter.com/CL0/https:%2F%2Fexample.com%2Fpost/1/0100019a626e0311">
    <strong>Why agent harnesses fail (6 minute read)</strong></a>
  <span>A walk through production agent design and where retries go wrong.</span>
</td></tr>
<tr><td><a href="https://example.com/post"><img src="x.png"></a></td></tr>
<tr><td><a href="https://acme.dev/launch"><span><b>Acme</b> <i>ships</i></span> Agent SDK</a>
  lets you build agents in ten lines.</td></tr>
</table></body></html>
"""


def _by_anchor(links: list[Link]) -> dict[str, Link]:
    return {link.anchor: link for link in links}


def test_extract_finds_every_anchor_in_order() -> None:
    links = extract(FIXTURE)
    assert [link.anchor for link in links] == [
        "Why agent harnesses fail (6 minute read)",
        "",
        "Acme ships Agent SDK",
    ]


def test_the_context_window_reaches_the_description_after_the_link() -> None:
    link = _by_anchor(extract(FIXTURE))["Why agent harnesses fail (6 minute read)"]
    assert "where retries go wrong" in link.context
    assert "where retries go wrong" in link.blurb


def test_zero_width_padding_never_reaches_the_context() -> None:
    for link in extract(FIXTURE):
        assert not newsletters._ZERO_WIDTH_RE.search(link.context)
    first = extract(FIXTURE)[0]
    assert first.context.startswith("Today's issue Why agent harnesses fail")


def test_nested_tags_collapse_to_their_text() -> None:
    link = _by_anchor(extract(FIXTURE))["Acme ships Agent SDK"]
    assert link.href == "https://acme.dev/launch"
    assert link.blurb.startswith("lets you build agents in ten lines.")


def test_an_empty_anchor_is_still_extracted_with_its_surroundings() -> None:
    link = _by_anchor(extract(FIXTURE))[""]
    assert link.href == "https://example.com/post"
    assert "where retries go wrong" in link.context


def test_entities_in_hrefs_are_decoded() -> None:
    [link] = extract('<a href="https://example.com/p?a=1&amp;b=2">Post</a>')
    assert link.href == "https://example.com/p?a=1&b=2"


def test_the_window_is_bounded_on_both_sides() -> None:
    html = f"{'x ' * 400}<a href='https://e.com'>A</a>{' y' * 400}"
    html = html.replace("'", '"')
    [link] = extract(html)
    assert (
        len(link.context)
        <= newsletters.CONTEXT_BEFORE + len("A") + newsletters.CONTEXT_AFTER
    )


# ─── prefilter ───────────────────────────────────────────────────────────────


def _link(href: str, anchor: str = "A story") -> Link:
    return Link(href=href, anchor=anchor, context="")


def test_prefilter_drops_plumbing_and_keeps_stories() -> None:
    links = [
        _link("mailto:editor@tldrnewsletter.com", "Email us"),
        _link("#top", "Back to top"),
        _link("https://tldrnewsletter.com/unsubscribe?ep=1", "Unsubscribe"),
        _link("https://example.org/manage", "Manage your preferences"),
        _link("https://x.com/tldrnewsletter", "Follow us"),
        _link("https://tldrnewsletter.com/ai", "Our AI edition"),
        _link("https://example.com/post?utm_source=tldr", "Post"),
        _link("https://example.com/post?utm_medium=email&utm_campaign=x", "Post"),
        _link(
            "https://tracking.tldrnewsletter.com/CL0/"
            "https:%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dabc/1/0100019a626e0311",
            "Watch the demo",
        ),
        _link("https://acme.dev/launch", ""),
        _link("https://acme.dev/launch", "Acme ships Agent SDK"),
    ]

    kept, dropped = prefilter(links, "tldrnewsletter.com")

    assert [link.anchor for link in kept] == ["Post", "Acme ships Agent SDK"]
    assert kept[0].href == "https://example.com/post?utm_source=tldr"
    reasons = {r: [link.anchor for link in ls] for r, ls in dropped.items()}
    assert reasons == {
        "non_http": ["Email us", "Back to top"],
        "admin": ["Unsubscribe", "Manage your preferences"],
        "denied": ["Follow us", "Watch the demo"],
        "own_host": ["Our AI edition"],
        "duplicate": ["Post"],
        "no_text": [""],
    }


def test_the_tracker_is_unwrapped_before_the_host_check() -> None:
    """The tracker lives on the newsletter's own domain; its destination does
    not, and the destination is what decides."""
    tracked = _link(
        "https://tracking.tldrnewsletter.com/CL0/"
        "https:%2F%2Fexample.com%2Fpost/1/0100019a626e0311"
    )
    kept, dropped = prefilter([tracked], "tldrnewsletter.com")
    assert kept == [tracked]
    assert dropped == {}


def test_a_tracked_link_and_a_direct_one_to_the_same_page_are_one() -> None:
    kept, dropped = prefilter(
        [
            _link(
                "https://tracking.tldrnewsletter.com/CL0/"
                "https:%2F%2Fexample.com%2Fpost%3Futm_source%3Dtldr/1/0100019a626e0311"
            ),
            _link("https://example.com/post/"),
        ],
        "tldrnewsletter.com",
    )
    assert len(kept) == 1
    assert len(dropped["duplicate"]) == 1


def test_an_opaque_tracker_is_kept_for_jev_to_judge() -> None:
    """Beehiiv hides the destination behind a token: no host to check, and the
    tracker's own host must not read as the sender's."""
    opaque = _link("https://link.mail.beehiiv.com/ss/c/u001.abcdef")
    kept, _ = prefilter([opaque], "mail.beehiiv.com")
    assert kept == [opaque]


# ─── verdict ─────────────────────────────────────────────────────────────────

_EDITORIAL: dict[str, jev.Json] = {
    "is_admin": 0.02,
    "is_sponsor": 0.05,
    "is_ai_topic": 0.95,
    "kind": "article",
    "is_first_party": 0.3,
    "is_notable": 0.9,
}


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "keep"),
        ({"is_sponsor": 0.74}, "keep"),
        ({"is_sponsor": 0.76}, "sponsor"),
        ({"is_admin": 0.54}, "keep"),
        ({"is_admin": 0.56}, "admin"),
        ({"is_ai_topic": 0.51}, "keep"),
        ({"is_ai_topic": 0.49}, "off_topic"),
        ({"kind": "product"}, "keep"),
        ({"kind": "neither"}, "neither"),
        ({"is_notable": 0.51}, "keep"),
        ({"is_notable": 0.49}, "not_notable"),
        ({"is_notable": 0.1, "is_ai_topic": 0.1}, "off_topic"),
        # The measured false positive at 0.5: a launch post that reads promotional.
        ({"is_sponsor": 0.64}, "keep"),
        ({"is_admin": 0.9, "is_sponsor": 0.9}, "admin"),
    ],
)
def test_verdict_thresholds(overrides: dict[str, jev.Json], expected: str) -> None:
    assert verdict({**_EDITORIAL, **overrides}) == expected


# ─── classification wiring ───────────────────────────────────────────────────


def test_extract_items_keeps_only_what_the_verdict_keeps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers: dict[str, dict[str, jev.Json]] = {
        "Sponsored: Try Acme free": {**_EDITORIAL, "is_sponsor": 0.96},
        "Acme ships Agent SDK": {
            **_EDITORIAL,
            "kind": "product",
            "is_first_party": 0.9,
        },
        "The Senior Engineer Death Spiral": {**_EDITORIAL, "is_ai_topic": 0.05},
    }
    seen_states: list[dict[str, str]] = []

    def ask(state: dict[str, str], _questions: object) -> jev.Reply:
        seen_states.append(state)
        return jev.Reply(answers=answers[state["link_text"]], cost=0.00002)

    monkeypatch.setattr(jev, "ask", ask)
    html = "".join(
        f'<p><a href="https://site{i}.com/p">{anchor}</a> blurb {i}.</p>'
        for i, anchor in enumerate(answers)
    )

    items = newsletters._extract_items(
        html, "TLDR AI", "2026-09-23", "tldrnewsletter.com"
    )

    assert len(seen_states) == 3
    assert {s["destination_host"] for s in seen_states} == {
        "site0.com",
        "site1.com",
        "site2.com",
    }
    [item] = items
    assert item["name"] == "Acme ships Agent SDK"
    assert item["kind"] == NewsletterItemKind.Product
    assert item["first_party"] is True
    assert item["description"].startswith("blurb 1.")


def test_a_failed_classification_drops_only_that_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def ask(state: dict[str, str], _questions: object) -> jev.Reply:
        if state["link_text"] == "Broken":
            raise jev.JevError("unanswered: is_sponsor")
        return jev.Reply(answers=_EDITORIAL, cost=0.0)

    monkeypatch.setattr(jev, "ask", ask)
    html = '<a href="https://a.com/1">Broken</a> <a href="https://b.com/2">Fine</a>'

    items = newsletters._extract_items(html, "TLDR AI", "2026-09-23", "tldr.tech")

    assert [i["name"] for i in items] == ["Fine"]


def test_an_opaque_tracker_is_never_first_party(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Jev saw "unknown" for the host, so its first-party answer is a guess."""
    monkeypatch.setattr(
        jev,
        "ask",
        lambda state, questions: jev.Reply(
            answers={**_EDITORIAL, "kind": "product", "is_first_party": 0.99}, cost=0
        ),
    )
    html = '<a href="https://link.mail.beehiiv.com/ss/c/u001.abc">Acme SDK</a>'

    [item] = newsletters._extract_items(html, "Pointer", "2026-09-23", "pointer.io")

    assert item["first_party"] is False


def test_an_article_about_privacy_is_not_a_privacy_policy() -> None:
    kept, _ = prefilter(
        [
            _link("https://example.com/blog/privacy-in-llms", "Privacy in LLMs"),
            _link("https://example.com/privacy", "Read more"),
        ],
        "tldrnewsletter.com",
    )
    assert [link.anchor for link in kept] == ["Privacy in LLMs"]


@pytest.mark.parametrize(
    ("sender", "own"),
    [
        ("dan@tldrnewsletter.com", "tldrnewsletter.com"),
        ("News@WWW.Example.com", "example.com"),
        ("writer@substack.com", ""),
        ("pointer@mail.beehiiv.com", ""),
    ],
)
def test_own_host_ignores_shared_sending_platforms(sender: str, own: str) -> None:
    """A Substack sender's own host would otherwise drop every post on every
    other Substack."""
    assert newsletters._own_host(sender) == own
