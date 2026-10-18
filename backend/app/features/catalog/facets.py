"""Facet counts for the feed's filters and rails: how many articles each publisher, tag and origin has, and who wrote them."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ColumnElement, func
from sqlmodel import Session, col, select

from app.core.db.article import Article, ArticleKind
from app.core.db.publisher import Publisher, PublisherKind
from app.core.db.tag import ArticleTag, Tag
from app.features.catalog.model import (
    ArticleFacets,
    FoundViaCount,
    Origin,
    OriginCount,
    OriginCounts,
    PublisherFacet,
    TagFacet,
    Voice,
    VoiceArticle,
    VoiceKind,
)
from app.features.catalog.rows import origin_condition


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


# A bar per article; past this many the row would outgrow the rail.
VOICE_SCORES = 15


def voices(
    session: Session, kind: VoiceKind, since: datetime, limit: int = 8
) -> list[Voice]:
    """The publishers of one kind with the most articles since `since`, busiest
    first and then by their best score: each with its scores oldest first and
    its best article."""
    conditions: list[ColumnElement[bool]] = [
        col(Article.published_at) >= since,
        col(Publisher.kind) == PublisherKind(kind.value),
    ]
    # On GitHub and Hugging Face the account is the publisher (ADR 13), so a
    # writer's repos and models would fill the tab with repo owners.
    if kind == VoiceKind.individual:
        conditions.append(col(Article.kind) == ArticleKind.post)

    count_expr = func.count(col(Article.id))
    best_expr = func.max(col(Article.score))
    top = session.exec(
        select(Publisher.id, Publisher.slug, Publisher.name, count_expr)
        .join(Article, col(Article.publisher_id) == col(Publisher.id))
        .where(*conditions)
        .group_by(col(Publisher.id))
        .order_by(count_expr.desc(), best_expr.desc(), col(Publisher.name))
        .limit(limit)
    ).all()
    if not top:
        return []

    articles = session.exec(
        select(Article)
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .where(*conditions, col(Article.publisher_id).in_([t[0] for t in top]))
        .order_by(col(Article.published_at), col(Article.id))
    ).all()
    by_publisher: dict[int | None, list[Article]] = {}
    for a in articles:
        by_publisher.setdefault(a.publisher_id, []).append(a)

    result = []
    for publisher_id, slug, name, count in top:
        rows = by_publisher[publisher_id]
        # Ties go to the newest: rows are oldest first and max keeps the first.
        best = max(reversed(rows), key=lambda a: a.score)
        result.append(
            Voice(
                slug=slug,
                name=name,
                count=count,
                scores=[a.score for a in rows[-VOICE_SCORES:]],
                best=VoiceArticle(
                    title=best.title,
                    url=best.url,
                    score=best.score,
                    published_at=best.published_at,
                ),
            )
        )
    return result
