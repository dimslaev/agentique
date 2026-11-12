"""Article search: by keyword and by meaning, fused into one ranking.

What stays hidden is the mechanism: Postgres full-text over the title, summary
and content, a pgvector distance to the query's embedding, and the reciprocal
rank fusion that merges the two rankings.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from model2vec import StaticModel
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import CTE, ColumnElement, cast, func
from sqlmodel import Session, col, select

from app.core.db.article import SEARCH_TSV, Article
from app.core.db.like import like_counts_subquery
from app.core.db.publisher import Publisher
from app.features.catalog.model import ArticlesPublic
from app.features.catalog.rows import build_rows, filter_conditions, liked_article_ids

# model2vec is CPU-only and small (~30 MB), so one process-wide instance loaded
# on first use costs less than a model server.
_MODEL_NAME = "minishlab/potion-base-8M"
_EMBEDDING_DIMS = 256

_MAX_LIMIT = 100
# How deep each ranking is read before the two are fused.
_POOL = _MAX_LIMIT
# From the reciprocal rank fusion paper: a row at `position` scores 1/(60+position).
_RRF_K = 60
_EXCERPT_CAP = 300
# About `_EXCERPT_CAP` characters of plain text, with no markup around the match.
_HEADLINE_OPTIONS = 'StartSel="", StopSel="", MaxWords=45, MinWords=20'

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
    return [float(x) for x in vec]


def _ranked(name: str, rank: ColumnElement[float], *where: ColumnElement[bool]) -> CTE:
    """The `_POOL` articles with the most `rank` among those passing `where`,
    numbered from 1."""
    order = (rank.desc(), col(Article.id).desc())
    return (
        select(
            col(Article.id).label("id"),
            func.row_number().over(order_by=order).label("position"),
        )
        .where(*where)
        .order_by(*order)
        .limit(_POOL)
        .cte(name)
    )


def _excerpt(headline: str) -> str | None:
    return " ".join(headline.split())[:_EXCERPT_CAP] or None


def search(
    session: Session,
    q: str,
    limit: int = 20,
    *,
    viewer_id: uuid.UUID | None = None,
    tags: list[str] | None = None,
    kinds: list[str] | None = None,
    since: datetime | None = None,
    publisher: str | None = None,
) -> ArticlesPublic:
    """Articles matching `q` by keyword, by meaning, or both, best first.

    The filters narrow the articles before they are ranked. `tags` and `kinds`
    each match any of their values.

    Each article carries an excerpt of its content around the keywords, or its
    opening words when only the title or the meaning matched. An article with
    no embedding yet is found by keyword only.
    """
    conditions = filter_conditions(
        since=since, kinds=kinds, tags=tags, publisher=publisher
    )
    # The unstemmed query is for the title's unstemmed entries.
    tsquery = func.websearch_to_tsquery("english", q).op("||")(
        func.websearch_to_tsquery("simple", q)
    )
    by_keyword = _ranked(
        "by_keyword",
        func.ts_rank(SEARCH_TSV, tsquery),
        *conditions,
        SEARCH_TSV.op("@@")(tsquery),
    )
    distance = cast(Article.embedding, Vector(_EMBEDDING_DIMS)).cosine_distance(
        embed(q)
    )
    # The distance is negated so that more is better. The HNSW index cannot
    # serve that order, which is wanted: it returns `hnsw.ef_search` rows at
    # most and filters them afterwards, so a narrow filter would leave few.
    by_meaning = _ranked(
        "by_meaning", -distance, *conditions, col(Article.embedding).is_not(None)
    )

    article_id = func.coalesce(by_keyword.c.id, by_meaning.c.id)
    score = func.coalesce(1.0 / (_RRF_K + by_keyword.c.position), 0) + func.coalesce(
        1.0 / (_RRF_K + by_meaning.c.position), 0
    )
    # On equal scores the keyword match goes first. The top of one ranking
    # always ties with the top of the other.
    order = (score.desc(), by_keyword.c.position.nulls_last(), article_id.desc())
    fused = (
        select(
            article_id.label("id"),
            func.row_number().over(order_by=order).label("position"),
        )
        .select_from(
            by_keyword.outerjoin(
                by_meaning, by_keyword.c.id == by_meaning.c.id, full=True
            )
        )
        .order_by(*order)
        .limit(min(limit, _MAX_LIMIT))
        .cte("fused")
    )

    like_counts_subq = like_counts_subquery()
    like_count_expr = func.coalesce(like_counts_subq.c.like_count, 0)
    headline = func.ts_headline(
        "english", func.coalesce(col(Article.content), ""), tsquery, _HEADLINE_OPTIONS
    )
    statement = (
        select(Article, Publisher, like_count_expr.label("like_count"), headline)
        .join(fused, fused.c.id == col(Article.id))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(like_counts_subq, like_counts_subq.c.article_id == Article.id)
        .order_by(fused.c.position)
    )

    rows = session.exec(statement).all()
    liked_ids = liked_article_ids(session, viewer_id) if viewer_id else set()
    data = build_rows(session, [(a, p, likes) for a, p, likes, _ in rows], liked_ids)
    for article, (_, _, _, text) in zip(data, rows, strict=True):
        article.excerpt = _excerpt(text)
    return ArticlesPublic(data=data, count=len(data))
