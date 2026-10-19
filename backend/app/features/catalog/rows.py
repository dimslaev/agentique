"""The ArticlePublic assembly and the origin filter that the feed, search and facets share.

`ArticlePublic` nests the publisher and the article's tags, so every endpoint
that returns articles (feed, search, liked) needs the same joins and the same
assembly. It lives apart from `service` so `semantic_search` and `facets` can
use it while `service` exposes them.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, select

from app.core.db.article import Article, ArticleKind
from app.core.db.like import ArticleLike
from app.core.db.publisher import Publisher, PublisherKind
from app.core.db.tag import ArticleTag, Tag
from app.features.catalog.model import (
    ArticlePublic,
    Origin,
    PublisherPublic,
    TagPublic,
)


def liked_article_ids(session: Session, user_id: uuid.UUID) -> set[int]:
    return set(
        session.exec(
            select(ArticleLike.article_id).where(ArticleLike.user_id == user_id)
        ).all()
    )


def tags_by_article(
    session: Session, article_ids: list[int]
) -> dict[int, list[TagPublic]]:
    """One query for every article's tags, keyed by article id."""
    if not article_ids:
        return {}
    rows = session.exec(
        select(ArticleTag.article_id, Tag.slug, Tag.name)
        .join(Tag, col(Tag.id) == col(ArticleTag.tag_id))
        .where(col(ArticleTag.article_id).in_(article_ids))
        .order_by(col(ArticleTag.article_id), col(Tag.slug))
    ).all()
    out: dict[int, list[TagPublic]] = defaultdict(list)
    for article_id, slug, name in rows:
        out[article_id].append(TagPublic(slug=slug, name=name))
    return out


def to_public(
    article: Article,
    publisher: Publisher,
    like_count: int,
    liked_by_me: bool,
    tags: list[TagPublic],
) -> ArticlePublic:
    assert article.id is not None
    assert publisher.id is not None
    return ArticlePublic(
        id=article.id,
        title=article.title,
        url=article.url,
        summary=article.summary,
        score=article.score,
        kind=article.kind,
        found_via=article.found_via,
        published_at=article.published_at,
        created_at=article.created_at,
        publisher=PublisherPublic(
            id=publisher.id,
            slug=publisher.slug,
            name=publisher.name,
            kind=publisher.kind,
            image=publisher.image,
        ),
        tags=tags,
        like_count=like_count,
        liked_by_me=liked_by_me,
    )


def build_rows(
    session: Session, rows: list[tuple[Article, Publisher, int]], liked_ids: set[int]
) -> list[ArticlePublic]:
    """`rows` are (Article, Publisher, like_count) tuples."""
    tags = tags_by_article(session, [a.id for a, _, _ in rows if a.id is not None])
    out = []
    for a, p, like_count in rows:
        assert a.id is not None
        out.append(to_public(a, p, like_count, a.id in liked_ids, tags.get(a.id, [])))
    return out


# The article kinds that are their own origin, whoever published them.
ARTIFACT_KINDS = {
    Origin.repo: ArticleKind.repo,
    Origin.paper: ArticleKind.paper,
    Origin.model: ArticleKind.model,
}


def origin_condition(origin: Origin) -> ColumnElement[bool]:
    """A repo, paper or model is that whoever published it; a post falls under
    its publisher's kind. Community aggregators show under media, and an
    `unknown` publisher under none until the curation agent names its kind."""
    if origin in ARTIFACT_KINDS:
        return col(Article.kind) == ARTIFACT_KINDS[origin]
    kinds = [PublisherKind(origin.value)]
    if origin == Origin.media:
        kinds.append(PublisherKind.community)
    return (col(Article.kind) == ArticleKind.post) & col(Article.publisher_id).in_(
        select(Publisher.id).where(col(Publisher.kind).in_(kinds))
    )
