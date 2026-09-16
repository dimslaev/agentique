"""The article read model: the feed query, the liked list, and the ArticlePublic assembly they share.

`ArticlePublic` nests the publisher and the article's tags, so every endpoint
that returns articles (feed, search, liked) needs the same joins and the same
assembly. It lives here so route modules never build it themselves, and so
`semantic_search` can reuse it without importing a route module's privates.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import ColumnElement, Subquery, cast, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Session, col, select

from app.audience.models import ArticleLike
from app.catalog.models import (
    Article,
    ArticlePublic,
    ArticlesPublic,
    ArticleTag,
    Publisher,
    PublisherPublic,
    Tag,
    TagPublic,
)


def like_counts_subquery() -> Subquery:
    return (
        select(ArticleLike.article_id, func.count().label("like_count"))
        .group_by(ArticleLike.article_id)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        .subquery()
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
        categories=article.categories,
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


def _filters(
    since: datetime | None,
    q: str | None,
    min_score: int | None,
    category: str | None,
    kind: str | None,
    tag: str | None,
    publisher: str | None,
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    # A text search is all-time. `since` is a browsing window the reader left
    # on from scrolling the feed, not a constraint they chose for this search,
    # and silently hiding the one article they typed the words of is worse than
    # ignoring it.
    if since is not None and not q:
        conditions.append(col(Article.published_at) >= since)
    if q:
        conditions.append(
            col(Article.title).ilike(f"%{q}%") | col(Article.content).ilike(f"%{q}%")
        )
    if min_score is not None:
        conditions.append(col(Article.score) >= min_score)
    if kind is not None:
        conditions.append(col(Article.kind) == kind)
    if category is not None:
        conditions.append(
            cast(Article.categories, JSONB).contains([category])  # type: ignore[arg-type]
        )
    if tag is not None:
        conditions.append(
            col(Article.id).in_(
                select(ArticleTag.article_id)
                .join(Tag, col(Tag.id) == col(ArticleTag.tag_id))
                .where(Tag.slug == tag)
            )
        )
    if publisher is not None:
        conditions.append(
            col(Article.publisher_id).in_(
                select(Publisher.id).where(Publisher.slug == publisher)
            )
        )
    return conditions


def list_articles(
    session: Session,
    *,
    viewer_id: uuid.UUID | None = None,
    limit: int = 20,
    since: datetime | None = None,
    q: str | None = None,
    min_score: int | None = None,
    category: str | None = None,
    kind: str | None = None,
    tag: str | None = None,
    publisher: str | None = None,
    sort: str = "score-desc",
) -> ArticlesPublic:
    """The feed: filtered, sorted, capped. `count` is the unlimited match total.

    `viewer_id` only decides whether `liked_by_me` is filled in — the feed is
    public and a token is optional.
    """
    conditions = _filters(since, q, min_score, category, kind, tag, publisher)

    count = session.exec(
        select(func.count()).select_from(Article).where(*conditions)
    ).one()

    like_counts_subq = like_counts_subquery()
    like_count_expr = func.coalesce(like_counts_subq.c.like_count, 0)
    statement = (
        select(Article, Publisher, like_count_expr.label("like_count"))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(like_counts_subq, like_counts_subq.c.article_id == Article.id)
        .where(*conditions)
    )

    if sort == "published_at-desc":
        statement = statement.order_by(
            col(Article.published_at).desc(), col(Article.id).desc()
        )
    elif sort == "likes-desc":
        statement = statement.order_by(
            like_count_expr.desc(), col(Article.score).desc(), col(Article.id).desc()
        )
    else:
        statement = statement.order_by(
            col(Article.score).desc(), col(Article.id).desc()
        )

    rows = session.exec(statement.limit(limit)).all()
    liked_ids = liked_article_ids(session, viewer_id) if viewer_id else set()
    return ArticlesPublic(data=build_rows(session, list(rows), liked_ids), count=count)


def list_liked_articles(session: Session, viewer_id: uuid.UUID) -> ArticlesPublic:
    """Every article this reader liked, most recently liked first."""
    like_counts_subq = like_counts_subquery()
    like_count_expr = func.coalesce(like_counts_subq.c.like_count, 0)

    statement = (
        select(Article, Publisher, like_count_expr.label("like_count"))
        .join(ArticleLike, col(ArticleLike.article_id) == col(Article.id))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(like_counts_subq, like_counts_subq.c.article_id == Article.id)
        .where(ArticleLike.user_id == viewer_id)
        .order_by(col(ArticleLike.created_at).desc(), col(Article.id).desc())
    )
    rows = session.exec(statement).all()

    # every row here is liked by definition
    liked_ids = {a.id for a, _, _ in rows if a.id is not None}
    data = build_rows(session, list(rows), liked_ids)
    return ArticlesPublic(data=data, count=len(data))


def stats(session: Session) -> dict[str, int | str | None]:
    """How many articles the catalog holds and when it last grew."""
    total = session.exec(select(func.count()).select_from(Article)).one()
    last = session.exec(
        select(func.max(Article.created_at))  # type: ignore[arg-type]
    ).one()
    return {"total": total, "lastUpdated": last.isoformat() if last else None}
