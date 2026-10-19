"""A reader's like on an article, and the per-article count the feed and newsletter read.

A like is a reader action: its lifecycle follows the user, not the article.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Subquery, func
from sqlmodel import Field, SQLModel, select

from app.core.dates import get_datetime_utc


class ArticleLike(SQLModel, table=True):
    __tablename__ = "article_like"
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    article_id: int = Field(foreign_key="article.id", primary_key=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


def like_counts_subquery() -> Subquery:
    return (
        select(ArticleLike.article_id, func.count().label("like_count"))
        .group_by(ArticleLike.article_id)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        .subquery()
    )
