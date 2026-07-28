"""Shared shape for the article dict that flows through the pipeline's steps.

Sources emit ``FetchedArticle``; each step adds a few keys as the article moves
through resolve -> filter -> categorize -> insert -> enrich. ``total=False``
because most keys are progressively populated, not present from the start --
this documents and typo-checks step signatures, it does not enforce stage
ordering (a step reading a not-yet-populated key is still a runtime KeyError,
same as before).

``summarize`` reshapes into the narrower, fully-populated ``ProcessedArticle``
that ``embed_articles`` consumes.
"""

from __future__ import annotations

from typing import TypedDict


class FetchedArticle(TypedDict, total=False):
    # set by every source fetcher
    title: str
    url: str
    content: str
    published_date: str | None
    source: str
    # set by _resolve_publishers
    publisher_id: int
    trust: str
    # set by match_categories — 1-3 category slugs. An article that reaches
    # insert always has at least one; that is the whole admission rule.
    categories: list[str]
    # set by _insert_articles
    id: int


class ProcessedArticle(TypedDict):
    id: int
    url: str
    title: str
    summary: str
    categories: list[str]
