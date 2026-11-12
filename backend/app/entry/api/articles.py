"""Article listing, search and facet endpoints for the public feed."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.entry.api.deps import CurrentUserOptional, SessionDep
from app.features.catalog.model import (
    ArticleFacets,
    ArticlesPublic,
    Origin,
    OriginCounts,
    PublisherFacet,
    TagFacet,
    Voice,
    VoiceKind,
)
from app.features.catalog.service import (
    all_facets,
    list_articles,
    origin_counts,
    publisher_facets,
    search,
    stats,
    tag_facets,
    voices,
)

router = APIRouter(prefix="/articles", tags=["articles"])

# Reads are public and unbounded. A caller may still send a token — it only
# decides whether `liked_by_me` is filled in.


def _parse_since(since: str) -> datetime:
    try:
        return datetime.fromisoformat(since)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid 'since' datetime")


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
    return list_articles(
        session,
        viewer_id=current_user.id if current_user else None,
        limit=limit,
        since=_parse_since(since) if since is not None else None,
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
    limit: int = Query(default=20, ge=1, le=100),
    # Repeatable, like the feed's: `?tag=a&tag=b` matches either.
    tag: list[str] | None = Query(default=None),
    kind: list[str] | None = Query(default=None),
    since: str | None = None,
    publisher: str | None = None,
) -> ArticlesPublic:
    return search(
        session,
        q,
        limit,
        viewer_id=current_user.id if current_user else None,
        tags=tag,
        kinds=kind,
        since=_parse_since(since) if since is not None else None,
        publisher=publisher,
    )


@router.get("/facets", response_model=ArticleFacets)
def article_facets(
    session: SessionDep, limit: int = Query(default=8, ge=1, le=20)
) -> ArticleFacets:
    return all_facets(session, limit)


@router.get("/origins", response_model=OriginCounts)
def article_origins(session: SessionDep, since: str) -> OriginCounts:
    return origin_counts(session, _parse_since(since))


@router.get("/voices", response_model=list[Voice])
def article_voices(
    session: SessionDep,
    kind: VoiceKind,
    since: str,
    limit: int = Query(default=8, ge=1, le=20),
) -> list[Voice]:
    return voices(session, kind, _parse_since(since), limit)


@router.get("/publishers", response_model=list[PublisherFacet])
def search_publishers(
    session: SessionDep,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[PublisherFacet]:
    return publisher_facets(session, q, limit)


@router.get("/tags", response_model=list[TagFacet])
def search_tags(
    session: SessionDep,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[TagFacet]:
    return tag_facets(session, q, limit)


@router.get("/stats")
def article_stats(session: SessionDep) -> dict[str, int | str | None]:
    return stats(session)
