"""Drop what we have already seen, before anything is spent on it.

A URL that is an Article, a pending candidate or a settled reject is never
fetched and judged again. Nothing else is filtered: the curation agent judges
topic, reach and duplicates itself, with `similar` and `coverage` to see what the
feed already carries (ADR 11).
"""

from __future__ import annotations

from sqlmodel import Session, col, select

from app.core.db.article import Article
from app.core.db.ledger import Reject
from app.core.logging import log
from app.features.collect.model import RawItem


def filter_known_urls[T: RawItem](
    session: Session, articles: list[T], label: str
) -> list[T]:
    if not articles:
        return []
    # The same post arrives with and without a trailing slash, from different
    # sources (kernel.dev came back as a new candidate on 2026-11-20).
    all_urls = [u for a in articles for u in _slash_variants(a["url"])]

    existing_urls = set(
        session.exec(select(Article.url).where(col(Article.url).in_(all_urls))).all()
    )
    scored_urls = set(
        session.exec(select(Reject.url).where(col(Reject.url).in_(all_urls))).all()
    )

    known = existing_urls | scored_urls
    fresh = [
        a for a in articles if not any(u in known for u in _slash_variants(a["url"]))
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


def _slash_variants(url: str) -> tuple[str, str]:
    """``url`` with and without its trailing slash. Pure."""
    bare = url.rstrip("/")
    return bare, f"{bare}/"
