"""Step 4: insert the articles that matched a category, with their categories."""

from __future__ import annotations

from sqlmodel import Session

from app.models import Article
from pipeline.categories import (
    MAX_CATEGORIES_PER_ARTICLE,
    Vocabulary,
    write_article_categories,
)
from pipeline.llm_text import sanitize_llm_text
from pipeline.types import FetchedArticle
from pipeline.utils import log, parse_date


def best_per_url(matched: list[FetchedArticle]) -> list[FetchedArticle]:
    """One article per URL, merging their categories. Pure: no I/O.

    Two sources can surface the same URL in one run (an HN post and a feed item
    for the same post); the URL is the identity. There is no score to break the
    tie any more, so the first occurrence wins on content and the categories are
    unioned — both judgements were made about the same article, and dropping one
    would lose a lane for no reason. The union is capped the same way a single
    match is.
    """
    by_url: dict[str, FetchedArticle] = {}
    for item in matched:
        existing = by_url.get(item["url"])
        if not existing:
            # Copied, not aliased: the union below writes back into this dict,
            # and a step must not mutate the list it was handed.
            by_url[item["url"]] = {**item}
            continue
        merged = list(existing.get("categories", []))
        for slug in item.get("categories", []):
            if slug not in merged:
                merged.append(slug)
        existing["categories"] = merged[:MAX_CATEGORIES_PER_ARTICLE]
    return list(by_url.values())


def insert_articles(
    session: Session, matched: list[FetchedArticle], vocab: Vocabulary
) -> list[FetchedArticle]:
    if not matched:
        return []

    inserted: list[FetchedArticle] = []
    for item in best_per_url(matched):
        title = sanitize_llm_text(item["title"])
        content = sanitize_llm_text(item.get("content") or "")
        article = Article(
            title=title,
            publisher_id=item["publisher_id"],
            url=item["url"],
            published_at=parse_date(item.get("published_date")),
            content=content,
        )
        session.add(article)
        session.flush()
        assert article.id is not None

        # Written here rather than in enrich: the categories are the reason the
        # article was admitted, so a row must never exist without them.
        write_article_categories(session, article.id, item["categories"], vocab)

        log(f"  Inserted #{article.id}: [{', '.join(item['categories'])}] {title}")
        inserted.append({**item, "id": article.id, "title": title, "content": content})

    session.commit()
    return inserted
