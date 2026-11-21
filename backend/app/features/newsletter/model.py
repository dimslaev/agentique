"""The newsletter's shapes: the week's articles, what readers liked, and the
errors the agent gets back as a message."""

from __future__ import annotations

from typing import TypedDict


class WeekArticle(TypedDict):
    url: str
    title: str
    publisher: str
    publisher_kind: str
    kind: str
    score: int
    likes: int
    summary: str


class LikedArticle(WeekArticle):
    published_at: str


class Week(TypedDict):
    articles: list[WeekArticle]
    liked: list[LikedArticle]


class IssueError(ValueError):
    """An issue that cannot be drafted as given, returned as a message."""
