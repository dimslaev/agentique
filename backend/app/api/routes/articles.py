from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from model2vec import StaticModel
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import cast, func, nullslast
from sqlmodel import Session, col, select

from app.api.article_view import (
    build_rows,
    like_counts_subquery,
    liked_article_ids,
)
from app.api.deps import CurrentUserOptional, SessionDep
from app.models import (
    Article,
    ArticleCategory,
    ArticleFacets,
    ArticlesPublic,
    Category,
    CategoryFacet,
    Publisher,
    PublisherFacet,
)

router = APIRouter(prefix="/articles", tags=["articles"])

# Reads are public and unbounded. A caller may still send a token — it only
# decides whether `liked_by_me` is filled in.

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
    q: str | None = None,
    category: str | None = None,
    kind: str | None = None,
    publisher: str | None = None,
    sort: str = Query(default="published_at-desc"),
) -> Any:
    # Missing `since` means "all time" (no lower bound).
    since_dt: datetime | None = None
    if since is not None:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid 'since' datetime")

    conditions: list[Any] = []
    if since_dt is not None:
        conditions.append(col(Article.published_at) >= since_dt)
    if q:
        conditions.append(
            col(Article.title).ilike(f"%{q}%") | col(Article.content).ilike(f"%{q}%")
        )
    if kind is not None:
        conditions.append(col(Article.kind) == kind)
    # A homepage lane is exactly this: one category, newest first. The old
    # frontend had to union several tag queries and merge them client-side;
    # membership is now decided at ingest, so it is one indexed join.
    if category is not None:
        conditions.append(
            col(Article.id).in_(
                select(ArticleCategory.article_id)
                .join(Category, col(Category.id) == col(ArticleCategory.category_id))
                .where(Category.slug == category)
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

    # NULLS LAST is load-bearing, not decoration. Postgres sorts NULLs FIRST on
    # a DESC order, `published_at` is nullable, and `parse_date` returns None
    # whenever a feed omits or malforms its pubDate. Since newest-first is now
    # the default sort, one undated article would otherwise pin itself to the
    # top of the feed and of every homepage lane, permanently.
    newest_first = nullslast(col(Article.published_at).desc())

    if sort == "likes-desc":
        joined_statement = joined_statement.order_by(
            like_count_expr.desc(),
            newest_first,
            col(Article.id).desc(),
        )
    else:
        joined_statement = joined_statement.order_by(
            newest_first, col(Article.id).desc()
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

    conditions = [Article.embedding.is_not(None)]  # type: ignore[union-attr]  # ty: ignore[unresolved-attribute]

    statement = (
        select(Article, Publisher, like_count_expr.label("like_count"))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(like_counts_subq, like_counts_subq.c.article_id == Article.id)
        .where(*conditions)
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


def _category_facets(
    session: Session, q: str | None, limit: int
) -> list[CategoryFacet]:
    """Every active category with its article count, in lane order.

    Ordered by `position`, not by count: the category list is the site's fixed
    editorial shape, so it should not reshuffle as articles arrive. Categories
    with no articles yet are included — an empty lane is information.
    """
    count_expr = func.count(col(ArticleCategory.article_id))
    statement = (
        select(Category.slug, Category.name, count_expr.label("count"))
        .outerjoin(
            ArticleCategory, col(ArticleCategory.category_id) == col(Category.id)
        )
        .where(col(Category.is_active).is_(True))
        .group_by(col(Category.id))
        .order_by(col(Category.position))
        .limit(limit)
    )
    if q:
        statement = statement.where(col(Category.name).ilike(f"%{q}%"))
    rows = session.exec(statement).all()
    return [CategoryFacet(slug=s, name=n, count=c) for s, n, c in rows]


@router.get("/facets", response_model=ArticleFacets)
def article_facets(
    session: SessionDep, limit: int = Query(default=8, ge=1, le=20)
) -> Any:
    return ArticleFacets(
        publishers=_publisher_facets(session, None, limit),
        categories=_category_facets(session, None, limit),
    )


@router.get("/publishers", response_model=list[PublisherFacet])
def search_publishers(
    session: SessionDep,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> Any:
    return _publisher_facets(session, q, limit)


@router.get("/categories", response_model=list[CategoryFacet])
def search_categories(
    session: SessionDep,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> Any:
    return _category_facets(session, q, limit)


@router.get("/stats")
def article_stats(session: SessionDep) -> Any:
    total = session.exec(select(func.count()).select_from(Article)).one()
    last = session.exec(
        select(func.max(Article.created_at))  # type: ignore[arg-type]
    ).one()
    return {"total": total, "lastUpdated": last.isoformat() if last else None}
