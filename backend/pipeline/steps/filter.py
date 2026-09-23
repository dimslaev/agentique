"""Step 2: drop what we have already seen.

A URL that is an Article, a pending candidate or a settled reject is never
fetched and judged again. Nothing else is filtered: the curation agent judges
topic, reach and duplicates itself, with `similar` and `stories` to see what the
feed already carries (ADR 11).
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.catalog.models import Article
from app.platform.logging import log
from pipeline.models import Reject
from pipeline.types import Candidate


def filter_known_urls(
    session: Session, articles: list[Candidate], label: str
) -> list[Candidate]:
    if not articles:
        return []
    all_urls = [a["url"] for a in articles]

    existing_urls = set(
        session.exec(select(Article.url).where(Article.url.in_(all_urls))).all()
    )
    scored_urls = set(
        session.exec(select(Reject.url).where(Reject.url.in_(all_urls))).all()
    )

    fresh = [
        a
        for a in articles
        if a["url"] not in existing_urls and a["url"] not in scored_urls
    ]

    if existing_urls or scored_urls:
        log(
            f"  Filtered {len(existing_urls)} known + {len(scored_urls)} already-scored URLs"
        )
    if not fresh:
        log(f"  No new articles from {label}")
        return []
    log(f"  {len(fresh)} new articles to process")
    return fresh
