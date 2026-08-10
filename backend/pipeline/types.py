"""Shared shape for the article dict that flows through the pipeline's steps.

Sources emit ``FetchedArticle``; each step adds a few keys as the article moves
through resolve -> filter -> dedup -> score -> insert -> enrich.
``total=False`` because most keys are progressively populated, not present
from the start -- this documents and typo-checks step signatures, it does not
enforce stage ordering (a step reading a not-yet-populated key is still a
runtime KeyError, same as before).

``categorize_and_tag_articles`` reshapes into the narrower, fully-populated
``ProcessedArticle`` that ``embed_articles`` consumes.
"""

from __future__ import annotations

from typing import TypedDict

from app.models import Category


class FetchedArticle(TypedDict, total=False):
    # set by every source fetcher
    title: str
    url: str
    content: str
    published_date: str | None
    source: str
    # pre-parsed outbound candidates for an aggregator item, best-first:
    # [{url, host, kind, text}]. Only AI News sets it (see sources/ainews.py).
    links: list[dict]
    # set by _resolve_publishers
    publisher_id: int
    trust: str
    # set by _score_articles
    score: int
    # set by _insert_articles
    id: int


class ProcessedArticle(TypedDict):
    id: int
    url: str
    title: str
    score: int
    snippet: str
    categories: list[Category]
