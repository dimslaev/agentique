"""Newsletter link extraction, rule prefilter and the Jev verdict.

Everything here is a pure function of a string or a dict: what counts as a
link and what text surrounds it, which links are plumbing by rule, and where
the classification thresholds cut. The thresholds were measured on two real
issues; the table below is their specification.
"""

from __future__ import annotations

import pytest

from pipeline.sources import email
from pipeline.sources.email import Link, extract, prefilter, verdict

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


def test_extract_finds_every_anchor_in_order():
    links = extract(FIXTURE)
    assert [link.anchor for link in links] == [
        "Why agent harnesses fail (6 minute read)",
        "",
        "Acme ships Agent SDK",
    ]


def test_the_context_window_reaches_the_description_after_the_link():
    link = _by_anchor(extract(FIXTURE))["Why agent harnesses fail (6 minute read)"]
    assert "where retries go wrong" in link.context
    assert "where retries go wrong" in link.blurb


def test_zero_width_padding_never_reaches_the_context():
    for link in extract(FIXTURE):
        assert not email._ZERO_WIDTH_RE.search(link.context)
    first = extract(FIXTURE)[0]
    assert first.context.startswith("Today's issue Why agent harnesses fail")


def test_nested_tags_collapse_to_their_text():
    link = _by_anchor(extract(FIXTURE))["Acme ships Agent SDK"]
    assert link.href == "https://acme.dev/launch"
    assert link.blurb.startswith("lets you build agents in ten lines.")


def test_an_empty_anchor_is_still_extracted_with_its_surroundings():
    link = _by_anchor(extract(FIXTURE))[""]
    assert link.href == "https://example.com/post"
    assert "where retries go wrong" in link.context


def test_entities_in_hrefs_are_decoded():
    [link] = extract('<a href="https://example.com/p?a=1&amp;b=2">Post</a>')
    assert link.href == "https://example.com/p?a=1&b=2"


def test_the_window_is_bounded_on_both_sides():
    html = f"{'x ' * 400}<a href='https://e.com'>A</a>{' y' * 400}"
    html = html.replace("'", '"')
    [link] = extract(html)
    assert len(link.context) <= email.CONTEXT_BEFORE + len("A") + email.CONTEXT_AFTER


# ─── prefilter ───────────────────────────────────────────────────────────────


def _link(href: str, anchor: str = "A story") -> Link:
    return Link(href=href, anchor=anchor, context="")


def test_prefilter_drops_plumbing_and_keeps_stories():
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


def test_the_tracker_is_unwrapped_before_the_host_check():
    """The tracker lives on the newsletter's own domain; its destination does
    not, and the destination is what decides."""
    tracked = _link(
        "https://tracking.tldrnewsletter.com/CL0/"
        "https:%2F%2Fexample.com%2Fpost/1/0100019a626e0311"
    )
    kept, dropped = prefilter([tracked], "tldrnewsletter.com")
    assert kept == [tracked]
    assert dropped == {}


def test_a_tracked_link_and_a_direct_one_to_the_same_page_are_one():
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


def test_an_opaque_tracker_is_kept_for_jev_to_judge():
    """Beehiiv hides the destination behind a token: no host to check, and the
    tracker's own host must not read as the sender's."""
    opaque = _link("https://link.mail.beehiiv.com/ss/c/u001.abcdef")
    kept, _ = prefilter([opaque], "mail.beehiiv.com")
    assert kept == [opaque]


# ─── verdict ─────────────────────────────────────────────────────────────────

_EDITORIAL = {
    "is_admin": 0.02,
    "is_sponsor": 0.05,
    "is_ai_topic": 0.95,
    "kind": "article",
    "is_first_party": 0.3,
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
        # The measured false positive at 0.5: a launch post that reads promotional.
        ({"is_sponsor": 0.64}, "keep"),
        ({"is_admin": 0.9, "is_sponsor": 0.9}, "admin"),
    ],
)
def test_verdict_thresholds(overrides, expected):
    assert verdict({**_EDITORIAL, **overrides}) == expected


# ─── classification wiring ───────────────────────────────────────────────────


def test_extract_items_keeps_only_what_the_verdict_keeps(monkeypatch):
    answers = {
        "Sponsored: Try Acme free": {**_EDITORIAL, "is_sponsor": 0.96},
        "Acme ships Agent SDK": {
            **_EDITORIAL,
            "kind": "product",
            "is_first_party": 0.9,
        },
        "The Senior Engineer Death Spiral": {**_EDITORIAL, "is_ai_topic": 0.05},
    }
    seen_states = []

    def ask(state, _questions):
        seen_states.append(state)
        return email.jev.Reply(answers=answers[state["link_text"]], cost=0.00002)

    monkeypatch.setattr(email.jev, "ask", ask)
    html = "".join(
        f'<p><a href="https://site{i}.com/p">{anchor}</a> blurb {i}.</p>'
        for i, anchor in enumerate(answers)
    )

    items = email._extract_items(html, "TLDR AI", "2026-09-23", "tldrnewsletter.com")

    assert len(seen_states) == 3
    assert {s["destination_host"] for s in seen_states} == {
        "site0.com",
        "site1.com",
        "site2.com",
    }
    [item] = items
    assert item["name"] == "Acme ships Agent SDK"
    assert item["kind"] == email.NewsletterItemKind.Product
    assert item["first_party"] is True
    assert item["description"].startswith("blurb 1.")


def test_a_failed_classification_drops_only_that_link(monkeypatch):
    def ask(state, _questions):
        if state["link_text"] == "Broken":
            raise email.jev.JevError("unanswered: is_sponsor")
        return email.jev.Reply(answers=_EDITORIAL, cost=0.0)

    monkeypatch.setattr(email.jev, "ask", ask)
    html = '<a href="https://a.com/1">Broken</a> <a href="https://b.com/2">Fine</a>'

    items = email._extract_items(html, "TLDR AI", "2026-09-23", "tldr.tech")

    assert [i["name"] for i in items] == ["Fine"]


def test_an_opaque_tracker_is_never_first_party(monkeypatch):
    """Jev saw "unknown" for the host, so its first-party answer is a guess."""
    monkeypatch.setattr(
        email.jev,
        "ask",
        lambda state, questions: email.jev.Reply(
            answers={**_EDITORIAL, "kind": "product", "is_first_party": 0.99}, cost=0
        ),
    )
    html = '<a href="https://link.mail.beehiiv.com/ss/c/u001.abc">Acme SDK</a>'

    [item] = email._extract_items(html, "Pointer", "2026-09-23", "pointer.io")

    assert item["first_party"] is False


def test_an_article_about_privacy_is_not_a_privacy_policy():
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
def test_own_host_ignores_shared_sending_platforms(sender, own):
    """A Substack sender's own host would otherwise drop every post on every
    other Substack."""
    assert email._own_host(sender) == own
