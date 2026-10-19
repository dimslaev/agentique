"""The newsletter's shapes: the week's topics, what relates to one, and the
errors the agent gets back as a message."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class DigestError(ValueError):
    """A request the agent can correct, returned as a message."""


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


class WeekTopic(TypedDict):
    # Distinct publishers carrying it this week, the ledger's included.
    coverage: int
    publishers: list[str]
    likes: int
    top_score: int
    articles: list[WeekArticle]
    covered_by: list[CoveredBy]


class RelatedRow(TypedDict):
    url: str
    title: str
    publisher: str
    publisher_kind: str
    kind: str
    stage: str
    score: int | None
    distance: float
    # Published rows: what a reader sees under the title.
    summary: NotRequired[str]
    # Rejected rows: why curation turned it down, e.g. as a retelling.
    reason: NotRequired[str]


class Related(TypedDict):
    url: str
    title: str
    rows: list[RelatedRow]


class IssueError(ValueError):
    """An issue that cannot be drafted as given, returned as a message."""
