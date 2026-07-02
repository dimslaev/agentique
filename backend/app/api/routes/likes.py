from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep
from app.models_agentique import Article, ArticleLike, ArticlePublic, ArticlesPublic

router = APIRouter(tags=["likes"])


@router.put("/articles/{article_id}/like")
def like_article(
    session: SessionDep, current_user: CurrentUser, article_id: int
) -> Any:
    article = session.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    existing = session.get(ArticleLike, (current_user.id, article_id))
    if not existing:
        session.add(ArticleLike(user_id=current_user.id, article_id=article_id))
        session.commit()

    return {"ok": True}


@router.delete("/articles/{article_id}/like")
def unlike_article(
    session: SessionDep, current_user: CurrentUser, article_id: int
) -> Any:
    existing = session.get(ArticleLike, (current_user.id, article_id))
    if existing:
        session.delete(existing)
        session.commit()

    return {"ok": True}


@router.get("/me/liked-articles", response_model=ArticlesPublic)
def read_liked_articles(session: SessionDep, current_user: CurrentUser) -> Any:
    statement = (
        select(Article)
        .join(ArticleLike, col(ArticleLike.article_id) == col(Article.id))
        .where(ArticleLike.user_id == current_user.id)
        .order_by(col(ArticleLike.created_at).desc())
    )
    articles = session.exec(statement).all()

    return ArticlesPublic(
        data=[ArticlePublic.model_validate(a) for a in articles],
        count=len(articles),
    )
