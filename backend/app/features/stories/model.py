"""The stories' shapes: what the rail reads, and what the stories agent reads and
writes."""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from sqlmodel import SQLModel


class StoryError(ValueError):
    """A save or close the agent can correct, returned as a message."""


class StoryArticlePublic(SQLModel):
    id: int
    title: str
    url: str
    publisher: str
    published_at: datetime | None = None
    score: int


class StoryPublic(SQLModel):
    slug: str
    name: str
    blurb: str
    article_count: int
    publisher_count: int
    first_at: datetime | None = None
    last_at: datetime | None = None
    # An article joined it in the last 24 hours.
    grew_today: bool
    # Newest first, at most `stories.STORY_ARTICLES` of `article_count`.
    articles: list[StoryArticlePublic]


class SavedStory(TypedDict):
    slug: str
    created: bool
    # URLs this call added; ones already in the story are not counted again.
    added: int
    article_count: int
