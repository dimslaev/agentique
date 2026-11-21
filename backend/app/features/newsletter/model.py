"""The newsletter's shapes: the week's topics, what readers liked, and the
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


class CoveredBy(TypedDict):
    """A ledger row on the same story: another outlet's copy, usually rejected
    as a retelling."""

    url: str
    title: str
    publisher: str
    publisher_kind: str
    score: int | None
    reason: str


class LikedArticle(WeekArticle):
    published_at: str


class WeekTopic(TypedDict):
    # Distinct publishers carrying it this week, past decisions included.
    publisher_count: int
    publishers: list[str]
    likes: int
    top_score: int
    articles: list[WeekArticle]
    covered_by: list[CoveredBy]


class Week(TypedDict):
    topics: list[WeekTopic]
    liked: list[LikedArticle]


class IssueError(ValueError):
    """An issue that cannot be drafted as given, returned as a message."""
