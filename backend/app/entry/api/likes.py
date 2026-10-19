"""Liking an article, and the signed-in reader's liked list."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.entry.api.deps import CurrentUser, SessionDep
from app.features.audience import service
from app.features.catalog.model import ArticlesPublic
from app.features.catalog.service import list_liked_articles

router = APIRouter(tags=["likes"])


@router.put("/articles/{article_id}/like")
def like_article(
    session: SessionDep, current_user: CurrentUser, article_id: int
) -> dict[str, bool]:
    liked = service.like_article(
        session=session, user_id=current_user.id, article_id=article_id
    )
    if not liked:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"ok": True}


@router.delete("/articles/{article_id}/like")
def unlike_article(
    session: SessionDep, current_user: CurrentUser, article_id: int
) -> dict[str, bool]:
    service.unlike_article(
        session=session, user_id=current_user.id, article_id=article_id
    )
    return {"ok": True}


@router.get("/me/liked-articles", response_model=ArticlesPublic)
def read_liked_articles(
    session: SessionDep, current_user: CurrentUser
) -> ArticlesPublic:
    return list_liked_articles(session, current_user.id)
