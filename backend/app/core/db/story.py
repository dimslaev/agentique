"""Stories: named threads that run over days or weeks, and the articles in them.

Wider than coverage (one event told by several outlets): an agent names and
keeps stories, see ADR 16.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index
from sqlmodel import Field, SQLModel

from app.core.dates import get_datetime_utc


class Story(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True)
    name: str
    blurb: str
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # When its newest article was published. What the rail orders by and what
    # "quiet" is measured from.
    last_article_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    closed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class StoryArticle(SQLModel, table=True):
    """An article in a story. At most one open story per article, enforced in
    `catalog.stories.save_story`: a closed story keeps its articles."""

    __tablename__ = "story_article"
    # The primary key leads with story_id; "which story holds this article" is
    # asked on every save.
    __table_args__ = (Index("ix_story_article_article_id", "article_id"),)
    story_id: int = Field(foreign_key="story.id", primary_key=True, ondelete="CASCADE")
    article_id: int = Field(
        foreign_key="article.id", primary_key=True, ondelete="CASCADE"
    )
    added_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
