"""Step 5: insert the articles that passed scoring and were summarized."""

from __future__ import annotations

from sqlmodel import Session

from app.catalog.models import Article
from app.platform.logging import log
from pipeline.freshness import parse_date
from pipeline.llm_text import sanitize_llm_text
from pipeline.types import Persisted, Scored, Summarized


def best_per_url[T: Scored](scored: list[T]) -> list[T]:
    """One article per URL, keeping the highest score. Pure: no I/O.

    Two sources can surface the same URL in one run (an HN post and a feed item
    for the same post); the URL is the identity, so the better-scoring one wins.
    """
    by_url: dict[str, T] = {}
    for item in scored:
        existing = by_url.get(item["url"])
        if not existing or item["score"] > existing["score"]:
            by_url[item["url"]] = item
    return list(by_url.values())


def insert_articles(session: Session, summarized: list[Summarized]) -> list[Persisted]:
    if not summarized:
        return []

    inserted: list[Persisted] = []
    for item in best_per_url(summarized):
        title = sanitize_llm_text(item["title"])
        content = sanitize_llm_text(item["content"])
        article = Article(
            title=title,
            publisher_id=item["publisher_id"],
            url=item["url"],
            published_at=parse_date(item["published_date"]),
            score=item["score"],
            score_reason=item["score_reason"],
            summary=item["summary"],
            content=content,
        )
        session.add(article)
        session.flush()
        assert article.id is not None
        log(f"  Inserted #{article.id}: [{item['score']}/100] {title}")
        inserted.append({**item, "id": article.id, "title": title, "content": content})

    session.commit()
    return inserted
