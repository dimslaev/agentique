"""Posting and linking against the real schema, with Bluesky stubbed."""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from sqlmodel import Session

from app.core.db.factories import create_random_publisher
from app.core.db.publisher import LinkPlatform
from app.features.social import bluesky, service
from app.features.social.bluesky import Profile
from app.features.social.model import SocialError

DIDS = {"eugeneyan.com": "did:plc:eugene", "hamel.bsky.social": "did:plc:hamel"}


class Stub:
    def __init__(self) -> None:
        self.posted: set[str] = set()
        self.created: list[tuple[str, Mapping[str, object]]] = []

    def resolve(self, handle: str) -> str:
        if handle not in DIDS:
            raise SocialError("Unable to resolve handle")
        return DIDS[handle]

    def profile(self, actor: str) -> Profile:
        return {"handle": actor, "did": DIDS[actor], "followersCount": 9}

    def create(
        self, token: str, did: str, collection: str, record: Mapping[str, object]
    ) -> str:
        self.created.append((collection, record))
        return f"at://{did}/{collection}/3abc"


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> Stub:
    s = Stub()
    monkeypatch.setattr(bluesky, "resolve", s.resolve)
    monkeypatch.setattr(bluesky, "profile", s.profile)
    monkeypatch.setattr(bluesky, "create", s.create)
    monkeypatch.setattr(bluesky, "card_urls", lambda actor, limit: s.posted)
    monkeypatch.setattr(bluesky, "login", lambda: ("tok", "did:plc:me"))
    return s


@pytest.mark.usefixtures("stub")
def test_mentions_get_byte_offsets_after_multibyte_text() -> None:
    text = "• evals @eugeneyan.com and @hamel.bsky.social."
    facets = service.mention_facets(text)
    raw = text.encode()
    spans = [raw[f["index"]["byteStart"] : f["index"]["byteEnd"]] for f in facets]
    assert spans == [b"@eugeneyan.com", b"@hamel.bsky.social"]
    assert facets[0]["features"][0]["did"] == "did:plc:eugene"


@pytest.mark.usefixtures("stub")
def test_an_email_is_not_a_mention() -> None:
    assert service.mention_facets("write to me@eugeneyan.com") == []


def test_hashtags_get_tag_facets() -> None:
    text = "• sandboxes by @a.dev #sandboxing #ai_agents, not a#b"
    facets = service.tag_facets(text)
    raw = text.encode()
    spans = [raw[f["index"]["byteStart"] : f["index"]["byteEnd"]] for f in facets]
    assert spans == [b"#sandboxing", b"#ai_agents"]
    assert facets[0]["features"][0] == {
        "$type": "app.bsky.richtext.facet#tag",
        "tag": "sandboxing",
    }


def test_unknown_mention_is_refused(stub: Stub) -> None:
    with pytest.raises(SocialError):
        service.post("by @nobody.example", "https://a.dev/x", "T", "D")
    assert stub.created == []


def test_post_carries_card_and_returns_web_link(stub: Stub) -> None:
    link = service.post("Evals @eugeneyan.com", "https://a.dev/x", "T", "D")
    [(collection, record)] = stub.created
    assert collection == "app.bsky.feed.post"
    assert record["embed"] == {
        "$type": "app.bsky.embed.external",
        "external": {"uri": "https://a.dev/x", "title": "T", "description": "D"},
    }
    assert link == "https://bsky.app/profile/agentique.ch/post/3abc"


def test_too_long_or_already_posted_is_refused(stub: Stub) -> None:
    with pytest.raises(SocialError, match="limit"):
        service.post("x" * 301, "https://a.dev/x", "T", "D")
    stub.posted = {"https://a.dev/x"}
    with pytest.raises(SocialError, match="Already posted"):
        service.post("ok", "https://a.dev/x", "T", "D")
    assert stub.created == []


def test_link_saves_handle_and_follows_no_one(db: Session, stub: Stub) -> None:
    p = create_random_publisher(db)
    msg = service.link_account(db, p.slug, "eugeneyan.com")
    db.refresh(p)
    assert p.links[LinkPlatform.bluesky] == "eugeneyan.com"
    assert stub.created == []
    assert msg == f"Linked {p.slug} to @eugeneyan.com"


@pytest.mark.parametrize(
    ("name", "website", "resolved", "searched"),
    [
        ("Eugene Yan Blog", "https://eugeneyan.com", ["eugeneyan.com"], "Eugene Yan"),
        ("someone", "https://github.com/someone", [], "someone"),
    ],
)
def test_find_account_asks_for_the_publishers_own_handle_only(
    db: Session,
    stub: Stub,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    website: str,
    resolved: list[str],
    searched: str,
) -> None:
    asked: list[str] = []
    queries: list[str] = []

    def resolve(handle: str) -> str:
        asked.append(handle)
        return stub.resolve(handle)

    monkeypatch.setattr(bluesky, "resolve", resolve)

    def search(q: str, _limit: int) -> list[Profile]:
        queries.append(q)
        return []

    monkeypatch.setattr(bluesky, "search", search)
    monkeypatch.setattr(bluesky, "profiles", lambda dids: [])
    p = create_random_publisher(db, name=name, links={LinkPlatform.website: website})
    service.find_account(db, p.slug)
    assert (asked, queries) == (resolved, [searched])
