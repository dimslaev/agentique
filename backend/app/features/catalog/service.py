"""The public feed's read verbs: the feed query, the liked list, search, facets and stats.

Search and the facet counts live in their own modules (`semantic_search`,
`facets`) and are exposed here, so entry imports one module per feature.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, func
from sqlmodel import Session, col, select

from app.core.db.article import Article
from app.core.db.like import ArticleLike, like_counts_subquery
from app.core.db.publisher import Publisher
from app.core.db.tag import ArticleTag, Tag
from app.features.catalog.facets import all_facets as all_facets
from app.features.catalog.facets import origin_counts as origin_counts
from app.features.catalog.facets import publisher_facets as publisher_facets
from app.features.catalog.facets import tag_facets as tag_facets
from app.features.catalog.facets import voices as voices
from app.features.catalog.model import ArticlesPublic, Origin
from app.features.catalog.rows import build_rows, liked_article_ids, origin_condition
from app.features.catalog.semantic_search import search as search


def _filters(
    since: datetime | None,
    q: str | None,
    min_score: int | None,
    origin: Origin | None,
    kinds: list[str] | None,
    tags: list[str] | None,
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
    if kinds:
        conditions.append(col(Article.kind).in_(kinds))
    if origin is not None:
        conditions.append(origin_condition(origin))
    if tags:
        conditions.append(
            col(Article.id).in_(
                select(ArticleTag.article_id)
                .join(Tag, col(Tag.id) == col(ArticleTag.tag_id))
                .where(col(Tag.slug).in_(tags))
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
    origin: Origin | None = None,
    kinds: list[str] | None = None,
    tags: list[str] | None = None,
    publisher: str | None = None,
    sort: str = "score-desc",
) -> ArticlesPublic:
    """The feed: filtered, sorted, capped. `count` is the unlimited match total.

    `kinds` and `tags` each match any of their values; the two still AND.

    `viewer_id` only decides whether `liked_by_me` is filled in — the feed is
    public and a token is optional.
    """
    conditions = _filters(since, q, min_score, origin, kinds, tags, publisher)

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
    last = session.exec(select(func.max(Article.created_at))).one()
    return {"total": total, "lastUpdated": last.isoformat() if last else None}
