from __future__ import annotations

from typing import TypedDict

from app.models import Category


class FetchedArticle(TypedDict):
    url: str
    title: str
    description: str | None
    content: str | None
    published_date: str
    publisher_id: int


class ProcessedArticle(FetchedArticle):
    id: int
    score: int
    description: str
    content: str
    categories: list[Category]
