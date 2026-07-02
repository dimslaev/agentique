from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query
from model2vec import StaticModel
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import cast, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models_agentique import Article, ArticlePublic, ArticlesPublic

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
    limit: int = Query(default=20, ge=1, le=50),
    since: str | None = None,
    min_score: int | None = Query(default=None, ge=1, le=10),
    category: str | None = None,
    kind: str | None = None,
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

    statement = (
        select(Article)
        .where(Article.score.is_not(None))  # type: ignore[union-attr]  # ty: ignore[unresolved-attribute]
        .where(col(Article.published_at) >= since_dt)
    )

    if min_score is not None:
        statement = statement.where(Article.score >= min_score)  # type: ignore[operator]  # ty: ignore[unsupported-operator]
    if kind is not None:
        statement = statement.where(Article.kind == kind)
    if category is not None:
        statement = statement.where(
            cast(Article.categories, JSONB).contains([category])  # type: ignore[arg-type]
        )

    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()

    if sort == "published_at-desc":
        statement = statement.order_by(col(Article.published_at).desc()).limit(limit)
    else:
        statement = statement.order_by(col(Article.score).desc()).limit(limit)
    articles = session.exec(statement).all()

    return ArticlesPublic(
        data=[ArticlePublic.model_validate(a) for a in articles],
        count=count,
    )


@router.get("/search", response_model=ArticlesPublic)
def search_articles(
    session: SessionDep,
    q: str,
    limit: int = Query(default=20, ge=1, le=50),
) -> Any:
    query_vec = _embed(q)

    statement = (
        select(Article)
        .where(Article.score.is_not(None))  # type: ignore[union-attr]  # ty: ignore[unresolved-attribute]
        .where(Article.embedding.is_not(None))  # type: ignore[union-attr]  # ty: ignore[unresolved-attribute]
        .order_by(cast(Article.embedding, Vector(256)).cosine_distance(query_vec))
        .limit(limit)
    )

    articles = session.exec(statement).all()

    return ArticlesPublic(
        data=[ArticlePublic.model_validate(a) for a in articles],
        count=len(articles),
    )


@router.get("/stats")
def article_stats(session: SessionDep) -> Any:
    total = session.exec(select(func.count()).select_from(Article)).one()
    last = session.exec(
        select(func.max(Article.created_at))  # type: ignore[arg-type]
    ).one()
    return {"total": total, "lastUpdated": last.isoformat() if last else None}
