"""The one piece of enrichment left after the curation agent writes the labels:
the embedding.

Local and best-effort: a failed embedding costs the field, never the article.
"""

from __future__ import annotations

from sqlmodel import Session

from app.catalog.models import Article
from app.platform.logging import log
from pipeline.embedding import embed_batch, to_embedding_text
from pipeline.types import ProcessedArticle


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
