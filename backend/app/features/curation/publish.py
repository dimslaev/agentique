"""Writing an approved article: the Article row, then its embedding.

The embedding is the one piece of enrichment left after the curation agent
writes the labels. Local and best-effort: a failed embedding costs the field,
never the article.
"""

from __future__ import annotations

from sqlmodel import Session

from app.core.dates import parse_date
from app.core.db.article import Article
from app.core.embedding import embed_batch, to_embedding_text
from app.core.llm_text import sanitize_llm_text
from app.core.logging import log
from app.features.curation.model import (
    Persisted,
    ProcessedArticle,
    Scored,
    Summarized,
)


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


def embed_articles(session: Session, items: list[ProcessedArticle]) -> None:
    if not items:
        return

    log(f"  Embedding {len(items)} articles...")

    texts = [to_embedding_text(item["title"], item.get("snippet")) for item in items]
    try:
        vecs = embed_batch(texts)
    except Exception as e:
        log(f"  Embed batch failed, continuing: {e}")
        return

    for item, vec in zip(items, vecs, strict=True):
        article = session.get(Article, item["id"])
        if article:
            article.embedding = vec
            session.add(article)

    session.commit()
