"""Semantic article search: an embedding of the query, nearest neighbours by cosine distance.

Search is a capability, so the module says it is semantic in its name. What
stays hidden is the mechanism: which embedding model, that it is normalised,
and that the ranking is a pgvector distance operator.
"""

from __future__ import annotations

import uuid

from model2vec import StaticModel
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import cast, func
from sqlmodel import Session, col, select

from app.catalog.articles import build_rows, like_counts_subquery, liked_article_ids
from app.catalog.models import Article, ArticlesPublic, Publisher

# model2vec is CPU-only and small (~30 MB), so one process-wide instance loaded
# on first use costs less than a model server.
_MODEL_NAME = "minishlab/potion-base-8M"
_EMBEDDING_DIMS = 256

_model: StaticModel | None = None


def get_model() -> StaticModel:  # pragma: no cover
    global _model
    if _model is None:
        _model = StaticModel.from_pretrained(_MODEL_NAME)
    return _model


def embed(text: str) -> list[float]:  # pragma: no cover
    import numpy as np

    vec = get_model().encode([text])[0]
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def search(
    session: Session,
    q: str,
    limit: int = 20,
    viewer_id: uuid.UUID | None = None,
) -> ArticlesPublic:
    """Articles nearest to `q` in embedding space, closest first.

    Articles with no embedding yet are invisible to search rather than ranked
    last: a null vector has no meaningful distance.
    """
    query_vec = embed(q)

    like_counts_subq = like_counts_subquery()
    like_count_expr = func.coalesce(like_counts_subq.c.like_count, 0)

    statement = (
        select(Article, Publisher, like_count_expr.label("like_count"))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(like_counts_subq, like_counts_subq.c.article_id == Article.id)
        .where(Article.embedding.is_not(None))  # type: ignore[union-attr]  # ty: ignore[unresolved-attribute]
        .order_by(
            cast(Article.embedding, Vector(_EMBEDDING_DIMS)).cosine_distance(query_vec),
            col(Article.id).desc(),
        )
        .limit(limit)
    )

    rows = session.exec(statement).all()
    liked_ids = liked_article_ids(session, viewer_id) if viewer_id else set()
    data = build_rows(session, list(rows), liked_ids)
    return ArticlesPublic(data=data, count=len(data))
