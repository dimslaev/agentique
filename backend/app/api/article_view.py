"""Shared read-side shaping for article responses.

`ArticlePublic` nests the publisher and the article's tags, so every endpoint
that returns articles (list, search, liked) needs the same joins and the same
assembly. Kept here so `articles.py` and `likes.py` don't import each other's
privates.
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    Article,
    ArticleLike,
    ArticlePublic,
    ArticleTag,
    Publisher,
    PublisherPublic,
    Tag,
    TagPublic,
)


def like_counts_subquery() -> Any:
    return (
        select(ArticleLike.article_id, func.count().label("like_count"))
        .group_by(ArticleLike.article_id)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        .subquery()
    )


def liked_article_ids(session: Session, user_id: Any) -> set[int]:
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
    session: Session, rows: list[Any], liked_ids: set[int]
) -> list[ArticlePublic]:
    """`rows` are (Article, Publisher, like_count) tuples."""
    tags = tags_by_article(session, [a.id for a, _, _ in rows if a.id is not None])
    return [
        to_public(a, p, like_count, a.id in liked_ids, tags.get(a.id, []))
        for a, p, like_count in rows
    ]
