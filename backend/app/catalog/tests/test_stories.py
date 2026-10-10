"""Stories: the schema, what the rail lists, what the agent may save, and the
story tools' write gate."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlmodel import Session, col, delete, func, select

from app.catalog import stories
from app.catalog.models import Article, Publisher, Story, StoryArticle
from app.catalog.tests.factories import create_random_article, create_random_publisher
from app.platform.db import engine
from app.platform.settings import settings
from tests.random_data import random_lower_string

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
# Slugs are unique per run: the tests share a database with whatever a
# developer restored, stories included.
RUN = random_lower_string()[:6]


def S(slug: str) -> str:
    return f"{slug}-{RUN}"


DIM = 256


@pytest.fixture
def made(db: Session) -> Generator[dict[str, list[int]]]:
    """Ids of what a test created, deleted afterwards with every story made
    meanwhile, so the next test starts from the same rows."""
    created: dict[str, list[int]] = {"articles": [], "publishers": []}
    before = db.exec(select(func.max(Story.id))).one() or 0
    yield created
    db.rollback()
    ours = select(Story.id).where(col(Story.id) > before)
    db.exec(delete(StoryArticle).where(col(StoryArticle.story_id).in_(ours)))  # type: ignore[call-overload]
    db.exec(delete(Story).where(col(Story.id) > before))  # type: ignore[call-overload]
    db.exec(delete(Article).where(col(Article.id).in_(created["articles"])))  # type: ignore[call-overload]
    db.exec(delete(Publisher).where(col(Publisher.id).in_(created["publishers"])))  # type: ignore[call-overload]
    db.commit()


def _publisher(db: Session, made: dict[str, list[int]]) -> Publisher:
    p = create_random_publisher(db)
    assert p.id is not None
    made["publishers"].append(p.id)
    return p


def _article(
    db: Session,
    made: dict[str, list[int]],
    publisher: Publisher,
    days_ago: float = 1,
    **overrides: object,
) -> Article:
    a = create_random_article(
        db,
        publisher_id=publisher.id,
        published_at=NOW - timedelta(days=days_ago),
        url=f"https://stories.example/{random_lower_string()}",
        **overrides,
    )
    assert a.id is not None
    made["articles"].append(a.id)
    return a


def _save(
    db: Session,
    slug: str,
    urls: list[str],
    name: str | None = None,
    blurb: str = "What it is. Why it matters now.",
    now: datetime = NOW,
) -> stories.SavedStory:
    name = name or slug.replace("-", " ").title()
    return stories.save_story(db, slug, name, blurb, urls, now=now)


def _story(
    db: Session, made: dict[str, list[int]], slug: str, days_ago: float = 1
) -> list[Article]:
    """A story the rail shows: three articles from two publishers."""
    p1, p2 = _publisher(db, made), _publisher(db, made)
    articles = [
        _article(db, made, p1, days_ago + 2),
        _article(db, made, p2, days_ago + 1),
        _article(db, made, p1, days_ago),
    ]
    _save(db, slug, [a.url for a in articles])
    return articles


def _mine(listed: list, slugs: set[str]) -> list[str]:
    return [s.slug for s in listed if s.slug in slugs]


# ─── Migration ───────────────────────────────────────────────────────────────


def test_the_migration_creates_both_tables():
    schema = inspect(engine)
    story = {c["name"] for c in schema.get_columns("story")}
    assert story >= {
        "id",
        "slug",
        "name",
        "blurb",
        "created_at",
        "updated_at",
        "last_article_at",
        "closed_at",
    }
    assert any(
        u["column_names"] == ["slug"] for u in schema.get_unique_constraints("story")
    )
    pk = schema.get_pk_constraint("story_article")
    assert sorted(pk["constrained_columns"]) == ["article_id", "story_id"]
    assert {c["name"] for c in schema.get_columns("story_article")} == {
        "story_id",
        "article_id",
        "added_at",
    }


# ─── list_stories ────────────────────────────────────────────────────────────


def test_list_needs_three_articles_from_two_publishers(
    db: Session, made: dict[str, list[int]]
):
    one_publisher = _publisher(db, made)
    p1, p2 = _publisher(db, made), _publisher(db, made)
    _save(
        db,
        S("one-outlet"),
        [_article(db, made, one_publisher).url for _ in range(3)],
    )
    _save(
        db, S("two-articles"), [_article(db, made, p1).url, _article(db, made, p2).url]
    )
    _story(db, made, S("shown"))

    listed = stories.list_stories(db, limit=20, now=NOW)
    assert _mine(listed, {S("one-outlet"), S("two-articles"), S("shown")}) == [
        S("shown")
    ]


def test_list_hides_closed_stories(db: Session, made: dict[str, list[int]]):
    _story(db, made, S("closed-one"))
    stories.close_story(db, S("closed-one"), now=NOW)

    assert _mine(stories.list_stories(db, limit=20, now=NOW), {S("closed-one")}) == []


def test_list_orders_by_newest_article_and_shapes_each_story(
    db: Session, made: dict[str, list[int]]
):
    older = _story(db, made, S("older"), days_ago=5)
    _story(db, made, S("newer"), days_ago=1)

    listed = stories.list_stories(db, limit=20, now=NOW)
    assert _mine(listed, {S("older"), S("newer")}) == [S("newer"), S("older")]

    shown = next(s for s in listed if s.slug == S("older"))
    assert shown.article_count == 3
    assert shown.publisher_count == 2
    assert [a.url for a in shown.articles] == [a.url for a in reversed(older)]
    assert shown.first_at == older[0].published_at
    assert shown.last_at == older[-1].published_at


def test_grew_today_reads_when_an_article_was_added(
    db: Session, made: dict[str, list[int]]
):
    _story(db, made, S("quiet"))
    later = NOW + timedelta(days=2)

    listed = stories.list_stories(db, limit=20, now=later)
    assert next(s for s in listed if s.slug == S("quiet")).grew_today is False

    _save(db, S("quiet"), [_article(db, made, _publisher(db, made)).url], now=later)
    listed = stories.list_stories(db, limit=20, now=later)
    assert next(s for s in listed if s.slug == S("quiet")).grew_today is True


def test_the_rail_caps_the_articles_it_sends(
    db: Session, made: dict[str, list[int]], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(stories, "STORY_ARTICLES", 8)
    p1, p2 = _publisher(db, made), _publisher(db, made)
    urls = [_article(db, made, p1 if i % 2 else p2, i).url for i in range(10)]
    _save(db, S("long-one"), urls)

    shown = next(
        s
        for s in stories.list_stories(db, limit=20, now=NOW)
        if s.slug == S("long-one")
    )
    assert shown.article_count == 10
    assert [a.url for a in shown.articles] == urls[:8]


def test_the_route_serves_the_list(
    client: TestClient, db: Session, made: dict[str, list[int]]
):
    _story(db, made, S("served"))

    r = client.get(f"{settings.API_V1_STR}/stories/", params={"limit": 20})
    assert r.status_code == 200
    story = next(s for s in r.json() if s["slug"] == S("served"))
    assert set(story["articles"][0]) == {
        "id",
        "title",
        "url",
        "publisher",
        "published_at",
        "score",
    }


# ─── save_story ──────────────────────────────────────────────────────────────


def test_save_creates_then_updates_in_place(db: Session, made: dict[str, list[int]]):
    p = _publisher(db, made)
    first, second = _article(db, made, p), _article(db, made, p)

    saved = _save(db, S("codemode"), [first.url], name="Codemode")
    assert saved == {
        "slug": S("codemode"),
        "created": True,
        "added": 1,
        "article_count": 1,
    }

    saved = _save(
        db,
        S("codemode"),
        [first.url, second.url],
        name="Code mode",
        blurb="Agents write code that calls tools. It saves tokens.",
    )
    assert saved == {
        "slug": S("codemode"),
        "created": False,
        "added": 1,
        "article_count": 2,
    }
    story = db.exec(select(Story).where(Story.slug == S("codemode"))).one()
    db.refresh(story)
    assert story.name == "Code mode"
    assert story.blurb == "Agents write code that calls tools. It saves tokens."


@pytest.mark.parametrize(
    ("slug", "name", "blurb", "message"),
    [
        ("Bad Slug", "Ok", "Fine.", "Bad slug"),
        ("trailing-", "Ok", "Fine.", "Bad slug"),
        ("ok", "one two three four five", "Fine.", "over 4 words"),
        ("ok", "  ", "Fine.", "name is empty"),
        ("ok", "Ok", "One. Two. Three.", "over 2 sentences"),
        ("ok", "Ok", "x" * 281, "over 280"),
        ("ok", "Ok", " ", "blurb is empty"),
    ],
)
def test_save_refuses_a_bad_label(
    db: Session,
    made: dict[str, list[int]],
    slug: str,
    name: str,
    blurb: str,
    message: str,
):
    url = _article(db, made, _publisher(db, made)).url
    with pytest.raises(stories.StoryError, match=message):
        stories.save_story(db, slug, name, blurb, [url], now=NOW)


def test_save_refuses_unknown_urls_and_writes_nothing(
    db: Session, made: dict[str, list[int]]
):
    known = _article(db, made, _publisher(db, made)).url
    with pytest.raises(stories.StoryError, match="Not a published article"):
        _save(db, S("nothing-written"), [known, "https://never.example/x"])
    db.rollback()
    assert (
        db.exec(select(Story).where(Story.slug == S("nothing-written"))).first() is None
    )


def test_save_refuses_a_new_story_with_no_articles(db: Session):
    with pytest.raises(stories.StoryError, match="at least one"):
        _save(db, S("empty"), [])


def test_an_article_sits_in_one_open_story(db: Session, made: dict[str, list[int]]):
    p = _publisher(db, made)
    shared, other = _article(db, made, p), _article(db, made, p)
    _save(db, S("first"), [shared.url])

    with pytest.raises(
        stories.StoryError, match=rf"another open story.*\({S('first')}\)"
    ):
        _save(db, S("second"), [other.url, shared.url])
    db.rollback()
    assert db.exec(select(Story).where(Story.slug == S("second"))).first() is None

    stories.close_story(db, S("first"), now=NOW)
    assert _save(db, S("second"), [shared.url])["created"] is True


def test_a_closed_story_cannot_be_saved_or_closed_again(
    db: Session, made: dict[str, list[int]]
):
    url = _article(db, made, _publisher(db, made)).url
    _save(db, S("done"), [url])
    stories.close_story(db, S("done"), now=NOW)

    with pytest.raises(stories.StoryError, match="closed"):
        _save(db, S("done"), [url])
    with pytest.raises(stories.StoryError, match="already closed"):
        stories.close_story(db, S("done"), now=NOW)
    with pytest.raises(stories.StoryError, match="No story"):
        stories.close_story(db, S("never-was"), now=NOW)


# ─── story_candidates ────────────────────────────────────────────────────────


def _near(axis: int, wobble: float = 0.0) -> list[float]:
    """A vector on one high axis, far from the seeded random ones."""
    v = np.zeros(DIM, dtype=np.float32)
    v[220 + axis] = 1.0
    v[255] = wobble
    return v.tolist()


def test_candidates_cluster_free_articles_and_name_the_story_they_reach(
    db: Session, made: dict[str, list[int]]
):
    p1, p2 = _publisher(db, made), _publisher(db, made)
    held = _article(db, made, p1, embedding=_near(0))
    _save(db, S("held"), [held.url])
    joins = _article(db, made, p2, embedding=_near(0, 0.1))
    a = _article(db, made, p1, embedding=_near(1))
    b = _article(db, made, p2, embedding=_near(1, 0.2))
    alone = _article(db, made, p1, embedding=_near(2))

    found = stories.story_candidates(db, days=14, now=NOW)

    mine = [s for s in found["open"] if s["slug"] == S("held")]
    assert [s["articles"][0]["url"] for s in mine] == [held.url]
    ours = {held.url, joins.url, a.url, b.url, alone.url}
    clusters = [
        c for c in found["clusters"] if {x["url"] for x in c["articles"]} & ours
    ]
    by_urls = {frozenset(x["url"] for x in c["articles"]): c for c in clusters}
    assert set(by_urls) == {frozenset({joins.url}), frozenset({a.url, b.url})}
    assert by_urls[frozenset({joins.url})]["near"] == [S("held")]
    assert by_urls[frozenset({a.url, b.url})]["near"] == []
    assert by_urls[frozenset({a.url, b.url})]["publishers"] == sorted(
        [p1.name, p2.name]
    )


# ─── Tool gate ───────────────────────────────────────────────────────────────


def test_save_story_tool_reports_what_it_did(
    db: Session, made: dict[str, list[int]], monkeypatch: pytest.MonkeyPatch
):
    from fastmcp.server.auth import AccessToken

    from app.mcp import tools

    monkeypatch.setattr(
        tools,
        "get_access_token",
        lambda: AccessToken(token="t", client_id="c", scopes=[tools.WRITE_SCOPE]),
    )
    url = _article(db, made, _publisher(db, made)).url
    slug = S("tool-made")
    assert tools.save_story(slug, "Tool made", "It works.", [url]) == (
        f"Created {slug}: added 1, 1 articles in all"
    )
    assert tools.close_story(slug) == f"Closed {slug}"
