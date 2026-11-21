"""Stories: named threads that run over days or weeks, for the right rail.

A story is wider than a duplicate group. A duplicate group is one event reported
by several publishers,
within `DEDUP_DIST_THRESHOLD`; a story is a theme a builder follows, which
takes judgment, so an agent names and keeps them (ADR 16). This module is what
that agent drives through the MCP tools in `app/entry/mcp/`, and what the
public rail reads.

An article sits in at most one open story. Postgres cannot say that without a
trigger (the rule spans two tables), so `save_story` enforces it; it is the
only writer.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, func, select

from app.core.db.article import Article
from app.core.db.publisher import Publisher
from app.core.db.story import Story, StoryArticle
from app.features.stories.model import (
    SavedStory,
    StoryArticlePublic,
    StoryError,
    StoryPublic,
)

# What the rail shows: a story carried by fewer is a duplicate group, or not yet a story.
MIN_ARTICLES = 3
MIN_PUBLISHERS = 2
# Articles per story on the rail, newest first. The panel shows six and
# "Show all" the rest, so this is a payload cap rather than a page size.
STORY_ARTICLES = 30
GREW_WINDOW = timedelta(hours=24)


SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_MAX = 60
NAME_WORDS = 4
BLURB_SENTENCES = 2
BLURB_CHARS = 280
# A sentence ends at . ! or ? followed by space and a capital, a digit or a
# quote. Close enough for two plain sentences; "e.g. Claude" would count two.
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“(])")


def _published(article_at: datetime | None, created_at: datetime) -> datetime:
    return article_at or created_at


# ─── Public read ─────────────────────────────────────────────────────────────


def list_stories(
    session: Session, limit: int = 5, now: datetime | None = None
) -> list[StoryPublic]:
    """Open stories with at least `MIN_ARTICLES` articles from
    `MIN_PUBLISHERS` publishers, the most recently active first."""
    now = now or datetime.now(UTC)
    stats = session.exec(
        select(
            Story,
            func.count(col(Article.id)),
            func.count(func.distinct(Article.publisher_id)),
            func.max(StoryArticle.added_at),
        )
        .join(StoryArticle, col(StoryArticle.story_id) == col(Story.id))
        .join(Article, col(Article.id) == col(StoryArticle.article_id))
        .where(col(Story.closed_at).is_(None))
        .group_by(col(Story.id))
        .having(func.count(col(Article.id)) >= MIN_ARTICLES)
        .having(func.count(func.distinct(Article.publisher_id)) >= MIN_PUBLISHERS)
        .order_by(col(Story.last_article_at).desc().nulls_last(), col(Story.id))
        .limit(limit)
    ).all()
    if not stats:
        return []

    # Every member, newest first: the rail shows the head, the span reads both ends.
    by_story: dict[int, list[StoryArticlePublic]] = defaultdict(list)
    for story_id, article, publisher in _members(
        session, [s.id for s, *_ in stats if s.id is not None]
    ):
        by_story[story_id].append(
            StoryArticlePublic(
                id=article.id or 0,
                title=article.title,
                url=article.url,
                publisher=publisher,
                published_at=_published(article.published_at, article.created_at),
                score=article.score,
            )
        )

    out: list[StoryPublic] = []
    for story, count, publishers, last_added in stats:
        articles = by_story[story.id or 0]
        out.append(
            StoryPublic(
                slug=story.slug,
                name=story.name,
                blurb=story.blurb,
                article_count=count,
                publisher_count=publishers,
                first_at=articles[-1].published_at,
                last_at=articles[0].published_at,
                grew_today=last_added >= now - GREW_WINDOW,
                articles=articles[:STORY_ARTICLES],
            )
        )
    return out


def _members(session: Session, story_ids: list[int]) -> list[tuple[int, Article, str]]:
    """Every article in these stories with its publisher's name, newest first."""
    return list(
        session.exec(
            select(StoryArticle.story_id, Article, Publisher.name)
            .join(Article, col(Article.id) == col(StoryArticle.article_id))
            .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
            .where(col(StoryArticle.story_id).in_(story_ids))
            .order_by(
                func.coalesce(Article.published_at, Article.created_at).desc(),
                col(Article.id).desc(),
            )
        ).all()
    )


# ─── Agent writes ────────────────────────────────────────────────────────────


def _validate(slug: str, name: str, blurb: str) -> tuple[str, str]:
    if len(slug) > SLUG_MAX or not SLUG.match(slug):
        raise StoryError(
            f"Bad slug {slug!r}: lowercase letters, digits and single hyphens, "
            f"up to {SLUG_MAX} characters, e.g. 'decision-models'."
        )
    name = " ".join(name.split())
    if not name:
        raise StoryError("The name is empty.")
    if len(name.split()) > NAME_WORDS:
        raise StoryError(
            f"Name {name!r} is over {NAME_WORDS} words: use the term people use."
        )
    blurb = " ".join(blurb.split())
    if not blurb:
        raise StoryError("The blurb is empty.")
    if len(blurb) > BLURB_CHARS:
        raise StoryError(f"The blurb is {len(blurb)} characters, over {BLURB_CHARS}.")
    if len(SENTENCE_BREAK.split(blurb)) > BLURB_SENTENCES:
        raise StoryError(f"The blurb is over {BLURB_SENTENCES} sentences.")
    return name, blurb


def save_story(
    session: Session,
    slug: str,
    name: str,
    blurb: str,
    urls: list[str],
    now: datetime | None = None,
) -> SavedStory:
    """Create a story, or rename, reblurb and add articles to an open one.

    All or nothing: an unknown URL, or an article already in another open
    story, refuses the whole call and nothing is written.
    """
    now = now or datetime.now(UTC)
    name, blurb = _validate(slug, name, blurb)
    urls = list(dict.fromkeys(u.strip() for u in urls if u.strip()))

    story = session.exec(select(Story).where(col(Story.slug) == slug)).first()
    if story is not None and story.closed_at is not None:
        raise StoryError(
            f"Story {slug!r} is closed. Start a new one under another slug."
        )
    if story is None and not urls:
        raise StoryError("A new story needs at least one article URL.")

    articles = (
        session.exec(select(Article).where(col(Article.url).in_(urls))).all()
        if urls
        else []
    )
    unknown = sorted(set(urls) - {a.url for a in articles})
    if unknown:
        raise StoryError("Not a published article: " + ", ".join(unknown))

    article_ids = [a.id for a in articles if a.id is not None]
    held = session.exec(
        select(Article.url, Story.slug)
        .join(StoryArticle, col(StoryArticle.article_id) == col(Article.id))
        .join(Story, col(Story.id) == col(StoryArticle.story_id))
        .where(
            col(StoryArticle.article_id).in_(article_ids),
            col(Story.closed_at).is_(None),
            col(Story.slug) != slug,
        )
    ).all()
    if held:
        raise StoryError(
            "Already in another open story: "
            + ", ".join(f"{url} ({other})" for url, other in sorted(held))
        )

    created = story is None
    if story is None:
        story = Story(slug=slug, name=name, blurb=blurb, created_at=now)
    story.name = name
    story.blurb = blurb
    story.updated_at = now
    session.add(story)
    session.flush()
    assert story.id is not None

    present = set(
        session.exec(
            select(StoryArticle.article_id).where(
                col(StoryArticle.story_id) == story.id
            )
        ).all()
    )
    added = [i for i in article_ids if i not in present]
    for article_id in added:
        session.add(
            StoryArticle(story_id=story.id, article_id=article_id, added_at=now)
        )
    session.flush()

    count, last = session.exec(
        select(
            func.count(col(Article.id)),
            func.max(func.coalesce(Article.published_at, Article.created_at)),
        )
        .join(StoryArticle, col(StoryArticle.article_id) == col(Article.id))
        .where(col(StoryArticle.story_id) == story.id)
    ).one()
    story.last_article_at = last
    session.add(story)
    session.commit()
    return {
        "slug": slug,
        "created": created,
        "added": len(added),
        "article_count": int(count),
    }


def close_story(session: Session, slug: str, now: datetime | None = None) -> None:
    """Close an open story. Its articles stay with it and are free to join
    another."""
    story = session.exec(select(Story).where(col(Story.slug) == slug)).first()
    if story is None:
        raise StoryError(f"No story {slug!r}.")
    if story.closed_at is not None:
        raise StoryError(f"Story {slug!r} is already closed.")
    story.closed_at = now or datetime.now(UTC)
    story.updated_at = story.closed_at
    session.add(story)
    session.commit()
