"""Facet counts for the feed's filters and rails: how many articles each publisher, tag and origin has."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ColumnElement, func
from sqlmodel import Session, col, select

from app.catalog.articles import origin_condition
from app.catalog.models import (
    Article,
    ArticleFacets,
    ArticleKind,
    ArticleTag,
    FoundViaCount,
    Origin,
    OriginCount,
    OriginCounts,
    Publisher,
    PublisherFacet,
    PublisherKind,
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


def origin_counts(session: Session, since: datetime) -> OriginCounts:
    """How the articles published since `since` split by origin and by how
    they were found. Each origin is counted with the From filter's own
    condition, so a row's number is what that filter shows for the window."""
    in_window = col(Article.published_at) >= since

    def count(*conditions: ColumnElement[bool]) -> int:
        return session.exec(
            select(func.count()).select_from(Article).where(in_window, *conditions)
        ).one()

    unlabelled = count(
        col(Article.kind) == ArticleKind.post,
        col(Article.publisher_id).in_(
            select(Publisher.id).where(Publisher.kind == PublisherKind.unknown)
        ),
    )
    found_via_rows = session.exec(
        select(Article.found_via, func.count())
        .where(in_window)
        .group_by(col(Article.found_via))
        .order_by(func.count().desc())
    ).all()
    return OriginCounts(
        since=since,
        total=count(),
        origins=[
            OriginCount(origin=o, count=count(origin_condition(o))) for o in Origin
        ],
        unlabelled=unlabelled,
        found_via=[FoundViaCount(name=n, count=c) for n, c in found_via_rows],
    )
