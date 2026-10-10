"""Article listing, semantic search, facet and story endpoints for the public feed."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.catalog import facets, semantic_search, stories
from app.catalog.articles import list_articles, stats
from app.catalog.models import (
    ArticleFacets,
    ArticlesPublic,
    Origin,
    OriginCounts,
    PublisherFacet,
    StoryPublic,
    TagFacet,
)
from app.deps import CurrentUserOptional, SessionDep

router = APIRouter(prefix="/articles", tags=["articles"])
stories_router = APIRouter(prefix="/stories", tags=["stories"])

# Reads are public and unbounded. A caller may still send a token — it only
# decides whether `liked_by_me` is filled in.


@router.get("/", response_model=ArticlesPublic)
def read_articles(
    session: SessionDep,
    current_user: CurrentUserOptional,
    limit: int = Query(default=20, ge=1, le=50),
    since: str | None = None,
    q: str | None = None,
    min_score: int | None = Query(default=None, ge=1, le=10),
    origin: Origin | None = None,
    # Repeatable: `?tag=a&tag=b` matches either. A feed topic is a set of these.
    kind: list[str] | None = Query(default=None),
    tag: list[str] | None = Query(default=None),
    publisher: str | None = None,
    sort: str = Query(default="score-desc"),
) -> ArticlesPublic:
    # Missing `since` means "all time" (no lower bound). So does any `since`
    # sent alongside `q` — see `_filters`, a search is never date-bounded.
    since_dt: datetime | None = None
    if since is not None:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid 'since' datetime")

    return list_articles(
        session,
        viewer_id=current_user.id if current_user else None,
        limit=limit,
        since=since_dt,
        q=q,
        min_score=min_score,
        origin=origin,
        kinds=kind,
        tags=tag,
        publisher=publisher,
        sort=sort,
    )


@router.get("/search", response_model=ArticlesPublic)
def search_articles(
    session: SessionDep,
    current_user: CurrentUserOptional,
    q: str,
    limit: int = Query(default=20, ge=1, le=50),
) -> ArticlesPublic:
    return semantic_search.search(
        session, q, limit, viewer_id=current_user.id if current_user else None
    )


@router.get("/facets", response_model=ArticleFacets)
def article_facets(
    session: SessionDep, limit: int = Query(default=8, ge=1, le=20)
) -> ArticleFacets:
    return facets.all_facets(session, limit)


@router.get("/origins", response_model=OriginCounts)
def article_origins(session: SessionDep, since: str) -> OriginCounts:
    try:
        since_dt = datetime.fromisoformat(since)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid 'since' datetime")
    return facets.origin_counts(session, since_dt)


@router.get("/publishers", response_model=list[PublisherFacet])
def search_publishers(
    session: SessionDep,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[PublisherFacet]:
    return facets.publisher_facets(session, q, limit)


@router.get("/tags", response_model=list[TagFacet])
def search_tags(
    session: SessionDep,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[TagFacet]:
    return facets.tag_facets(session, q, limit)


@router.get("/stats")
def article_stats(session: SessionDep) -> dict[str, int | str | None]:
    return stats(session)


@stories_router.get("/", response_model=list[StoryPublic])
def read_stories(
    session: SessionDep, limit: int = Query(default=5, ge=1, le=20)
) -> list[StoryPublic]:
    return stories.list_stories(session, limit)
