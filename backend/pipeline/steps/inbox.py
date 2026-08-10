"""Step 0: put everything a source emitted into the curation agent's inbox.

This is the whole of the pipeline's job under the agent-driven design: fetch,
skip URLs we already have, insert. No scoring, no categorizing, no content
re-fetch — a thin row is a normal row, and the agent fetches what it decides it
needs.

It runs before the LLM funnel and is independent of it: the inbox commits on
its own, so a later step blowing up (and rolling its session back) still leaves
the agent a complete inbox for that source.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, delete, select

from app.models import Article, FeedItem
from pipeline.types import FetchedArticle
from pipeline.utils import log, parse_date

# How long a decided (or undecided) feed item is kept before pruning. Long
# enough to look back over a bad week, short enough that the inbox stays small.
RETENTION_DAYS = 30


def known_urls(session: Session, urls: list[str]) -> set[str]:
    """The subset of ``urls`` we have already seen.

    Deliberately URL-only: there is no semantic dedup on the way in, because
    "is this the same story we already published?" is a judgment call and the
    agent makes it (against ``/articles/search``) for the handful of items it
    actually wants, not for all ~100 that arrive.
    """
    if not urls:
        return set()
    seen = set(
        session.exec(select(FeedItem.url).where(col(FeedItem.url).in_(urls))).all()
    )
    seen |= set(
        session.exec(select(Article.url).where(col(Article.url).in_(urls))).all()
    )
    return seen


def record_feed_items(
    session: Session, articles: list[FetchedArticle], label: str
) -> int:
    """Insert every unseen item as a `new` feed item. Returns how many landed.

    ``publisher_id`` must already be stamped on each item (the fetch step's
    ``resolve_publishers`` does it) — it is recorded as the *carrier*, the
    publisher whose feed we found the item in, which for Hacker News and AI
    News is not the publisher of the article itself.
    """
    if not articles:
        return 0

    urls = list(dict.fromkeys(a["url"] for a in articles if a.get("url")))
    seen = known_urls(session, urls)

    inserted = 0
    for item in articles:
        url = item.get("url")
        if not url or url in seen:
            continue
        seen.add(url)  # two sources can surface one URL in a single run
        session.add(
            FeedItem(
                url=url,
                title=item["title"],
                content=item.get("content") or None,
                published_at=parse_date(item.get("published_date")),
                feed_publisher_id=item.get("publisher_id"),
                links=item.get("links") or [],
            )
        )
        inserted += 1

    session.commit()
    log(
        f"  {label}: {inserted} new feed item(s) ({len(urls) - inserted} already known)"
    )
    return inserted


def prune_feed_items(session: Session, days: int = RETENTION_DAYS) -> int:
    """Delete feed items older than ``days``. Returns how many went."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = session.exec(
        delete(FeedItem).where(col(FeedItem.fetched_at) < cutoff)  # type: ignore[call-overload]
    )
    session.commit()
    removed = result.rowcount or 0
    if removed:
        log(f"Pruned {removed} feed item(s) older than {days} days")
    return removed
