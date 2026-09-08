"""Step 4: insert the articles that passed scoring."""

from __future__ import annotations

from sqlmodel import Session

from app.models import Article
from app.platform.logging import log
from pipeline.freshness import parse_date
from pipeline.llm_text import sanitize_llm_text
from pipeline.types import FetchedArticle


def best_per_url(scored: list[FetchedArticle]) -> list[FetchedArticle]:
    """One article per URL, keeping the highest score. Pure: no I/O.

    Two sources can surface the same URL in one run (an HN post and a feed item
    for the same post); the URL is the identity, so the better-scoring one wins.
    """
    by_url: dict[str, FetchedArticle] = {}
    for item in scored:
        existing = by_url.get(item["url"])
        if not existing or item["score"] > existing["score"]:
            by_url[item["url"]] = item
    return list(by_url.values())


def insert_articles(
    session: Session, scored: list[FetchedArticle]
) -> list[FetchedArticle]:
    if not scored:
        return []

    inserted: list[FetchedArticle] = []
    for item in best_per_url(scored):
        title = sanitize_llm_text(item["title"])
        content = sanitize_llm_text(item.get("content") or "")
        article = Article(
            title=title,
            publisher_id=item["publisher_id"],
            url=item["url"],
            published_at=parse_date(item.get("published_date")),
            score=item["score"],
            content=content,
        )
        session.add(article)
        session.flush()
        assert article.id is not None
        log(f"  Inserted #{article.id}: [{item['score']}/100] {title}")
        inserted.append({**item, "id": article.id, "title": title, "content": content})

    session.commit()
    return inserted
