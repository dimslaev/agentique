"""Shared shape for the article dict that flows through the pipeline's steps.

Sources emit ``FetchedArticle``; each step adds a few keys as the article moves
through resolve -> filter -> dedup -> score -> insert -> enrich.
``total=False`` because most keys are progressively populated, not present
from the start -- this documents and typo-checks step signatures, it does not
enforce stage ordering (a step reading a not-yet-populated key is still a
runtime KeyError, same as before).

``_summarize_and_categorize`` reshapes into the narrower, fully-populated
``ProcessedArticle`` that ``_assign_tags``/``_embed_articles`` consume.
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
    # set by _resolve_publishers
    publisher_id: int
    trust: str
    # set by _score_articles
    score: int
    # set by _insert_articles
    id: int
    # set by _extract_full_content
    full_content: str


class ProcessedArticle(TypedDict):
    id: int
    url: str
    title: str
    score: int
    summary: str
    categories: list[Category]
