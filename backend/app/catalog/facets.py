"""Facet counts for the feed's filter sidebar: how many articles each publisher and tag has."""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.catalog.models import (
    Article,
    ArticleFacets,
    ArticleTag,
    Publisher,
    PublisherFacet,
    Tag,
    TagFacet,
)


def publisher_facets(
    session: Session, q: str | None = None, limit: int = 20
) -> list[PublisherFacet]:
    """Publishers by article count, busiest first; `q` filters by name."""
    count_expr = func.count(col(Article.id))
    statement = (
        select(Publisher.slug, Publisher.name, count_expr.label("count"))
        .join(Article, col(Article.publisher_id) == col(Publisher.id))
        .group_by(col(Publisher.id))
        .order_by(count_expr.desc())
        .limit(limit)
    )
    if q:
        statement = statement.where(col(Publisher.name).ilike(f"%{q}%"))
    rows = session.exec(statement).all()
    return [PublisherFacet(slug=s, name=n, count=c) for s, n, c in rows]


def tag_facets(
    session: Session, q: str | None = None, limit: int = 20
) -> list[TagFacet]:
    """Tags by article count, busiest first; `q` filters by name."""
    count_expr = func.count(col(ArticleTag.article_id))
    statement = (
        select(Tag.slug, Tag.name, count_expr.label("count"))
        .join(ArticleTag, col(ArticleTag.tag_id) == col(Tag.id))
        .group_by(col(Tag.id))
        .order_by(count_expr.desc())
        .limit(limit)
    )
    if q:
        statement = statement.where(col(Tag.name).ilike(f"%{q}%"))
    rows = session.exec(statement).all()
    return [TagFacet(slug=s, name=n, count=c) for s, n, c in rows]


def all_facets(session: Session, limit: int = 8) -> ArticleFacets:
    """Both facet lists in one response — what the sidebar renders on load."""
    return ArticleFacets(
        publishers=publisher_facets(session, None, limit),
        tags=tag_facets(session, None, limit),
    )
