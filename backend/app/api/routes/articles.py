from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from model2vec import StaticModel
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import cast, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Session, col, select

from app.api.article_view import (
    build_rows,
    like_counts_subquery,
    liked_article_ids,
)
from app.api.deps import CurrentUserOptional, SessionDep
from app.models import (
    Article,
    ArticleFacets,
    ArticlesPublic,
    ArticleTag,
    Publisher,
    PublisherFacet,
    Tag,
    TagFacet,
)

router = APIRouter(prefix="/articles", tags=["articles"])

# Loaded once at module import — model2vec is CPU-only and tiny (~30 MB)
_model: StaticModel | None = None


def get_model() -> StaticModel:  # pragma: no cover
    global _model
    if _model is None:
        _model = StaticModel.from_pretrained("minishlab/potion-base-8M")
    return _model


def _embed(text: str) -> list[float]:  # pragma: no cover
    import numpy as np

    model = get_model()
    vec = model.encode([text])[0]
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


@router.get("/", response_model=ArticlesPublic)
def read_articles(
    session: SessionDep,
    current_user: CurrentUserOptional,
    limit: int = Query(default=20, ge=1, le=50),
    since: str | None = None,
    min_score: int | None = Query(default=None, ge=1, le=10),
    category: str | None = None,
    kind: str | None = None,
    tag: str | None = None,
    publisher: str | None = None,
    sort: str = Query(default="score-desc"),
) -> Any:
    since_dt: datetime
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            since_dt = datetime.now(UTC) - timedelta(days=30)
    else:
        since_dt = datetime.now(UTC) - timedelta(days=30)

    conditions = [col(Article.published_at) >= since_dt]
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

    count_statement = select(func.count()).select_from(Article).where(*conditions)
    count = session.exec(count_statement).one()

    like_counts_subq = like_counts_subquery()
    like_count_expr = func.coalesce(like_counts_subq.c.like_count, 0)
    joined_statement = (
        select(Article, Publisher, like_count_expr.label("like_count"))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(like_counts_subq, like_counts_subq.c.article_id == Article.id)
        .where(*conditions)
    )

    if sort == "published_at-desc":
        joined_statement = joined_statement.order_by(
            col(Article.published_at).desc(), col(Article.id).desc()
        )
    elif sort == "likes-desc":
        joined_statement = joined_statement.order_by(
            like_count_expr.desc(), col(Article.score).desc(), col(Article.id).desc()
        )
    else:
        joined_statement = joined_statement.order_by(
            col(Article.score).desc(), col(Article.id).desc()
        )
    joined_statement = joined_statement.limit(limit)

    rows = session.exec(joined_statement).all()
    liked_ids = liked_article_ids(session, current_user.id) if current_user else set()

    return ArticlesPublic(data=build_rows(session, list(rows), liked_ids), count=count)


@router.get("/search", response_model=ArticlesPublic)
def search_articles(
    session: SessionDep,
    current_user: CurrentUserOptional,
    q: str,
    limit: int = Query(default=20, ge=1, le=50),
) -> Any:
    query_vec = _embed(q)

    like_counts_subq = like_counts_subquery()
    like_count_expr = func.coalesce(like_counts_subq.c.like_count, 0)

    statement = (
        select(Article, Publisher, like_count_expr.label("like_count"))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(like_counts_subq, like_counts_subq.c.article_id == Article.id)
        .where(Article.embedding.is_not(None))  # type: ignore[union-attr]  # ty: ignore[unresolved-attribute]
        .order_by(
            cast(Article.embedding, Vector(256)).cosine_distance(query_vec),
            col(Article.id).desc(),
        )
        .limit(limit)
    )

    rows = session.exec(statement).all()
    liked_ids = liked_article_ids(session, current_user.id) if current_user else set()

    data = build_rows(session, list(rows), liked_ids)
    return ArticlesPublic(data=data, count=len(data))


def _publisher_facets(
    session: Session, q: str | None, limit: int
) -> list[PublisherFacet]:
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


def _tag_facets(session: Session, q: str | None, limit: int) -> list[TagFacet]:
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


@router.get("/facets", response_model=ArticleFacets)
def article_facets(
    session: SessionDep, limit: int = Query(default=8, ge=1, le=20)
) -> Any:
    return ArticleFacets(
        publishers=_publisher_facets(session, None, limit),
        tags=_tag_facets(session, None, limit),
    )


@router.get("/publishers", response_model=list[PublisherFacet])
def search_publishers(
    session: SessionDep,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> Any:
    return _publisher_facets(session, q, limit)


@router.get("/tags", response_model=list[TagFacet])
def search_tags(
    session: SessionDep,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> Any:
    return _tag_facets(session, q, limit)


@router.get("/stats")
def article_stats(session: SessionDep) -> Any:
    total = session.exec(select(func.count()).select_from(Article)).one()
    last = session.exec(
        select(func.max(Article.created_at))  # type: ignore[arg-type]
    ).one()
    return {"total": total, "lastUpdated": last.isoformat() if last else None}
