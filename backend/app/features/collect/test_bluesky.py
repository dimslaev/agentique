"""The Bluesky post -> items conversion: links out, topic gate, window."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from app.features.collect import bluesky
from app.features.collect.bluesky import Card, Facet, Page, Post, to_items

NOW = datetime.now(UTC).isoformat()


def post(
    text: str, created: str = NOW, card: Card | None = None, links: Sequence[str] = ()
) -> Post:
    facets = [
        Facet(features=[{"$type": "app.bsky.richtext.facet#link", "uri": u}])
        for u in links
    ]
    p: Post = {
        "author": {"handle": "someone.bsky.social"},
        "record": {"text": text, "createdAt": created, "facets": facets},
        "likeCount": 4,
        "repostCount": 1,
    }
    if card:
        p["embed"] = {"external": card}
    return p


def test_link_card_gives_its_title() -> None:
    card: Card = {
        "uri": "https://example.com/a",
        "title": "Fine-tuning Qwen3",
        "description": "",
    }
    [item] = to_items(post("worth a read", card=card, links=["https://example.com/a"]))
    assert item["url"] == "https://example.com/a"
    assert item["title"] == "Fine-tuning Qwen3"
    assert item["source"] == "Bluesky"
    assert "4 likes, 1 reposts" in item["traction"]


def test_every_link_in_text_is_an_item() -> None:
    items = to_items(
        post(
            "my new LLM eval harness", links=["https://a.dev", "https://github.com/x/y"]
        )
    )
    assert [i["url"] for i in items] == ["https://a.dev", "https://github.com/x/y"]
    assert items[0]["title"] == "my new LLM eval harness"


def test_skips_off_topic_no_link_bsky_link_and_old() -> None:
    old = (datetime.now(UTC) - timedelta(days=5)).isoformat()
    assert to_items(post("climate summit ends", links=["https://news.example"])) == []
    assert to_items(post("Claude is great")) == []
    assert (
        to_items(post("Claude thread", links=["https://bsky.app/profile/x/post/1"]))
        == []
    )
    assert (
        to_items(post("Claude story", links=["https://www.techmeme.com/261123/p3"]))
        == []
    )
    assert to_items(post("Claude post", created=old, links=["https://a.dev"])) == []


def test_fetch_reads_every_follow_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    feeds = {
        "did:a": [post("Claude tips", links=["https://a.dev"])],
        "did:b": [post("more Claude", links=["https://a.dev", "https://b.dev"])],
    }

    def fake_get(method: str, **params: str | int) -> Page:
        if method == "app.bsky.graph.getFollows":
            return {"follows": [{"did": d} for d in feeds]}
        return {"feed": [{"post": p} for p in feeds[str(params["actor"])]]}

    monkeypatch.setattr(bluesky, "_get", fake_get)
    items = bluesky.fetch_bluesky("agentique.ch")
    assert sorted(i["url"] for i in items) == ["https://a.dev", "https://b.dev"]
