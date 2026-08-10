"""Step 1: poll the sources, and resolve each item's publisher."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session

from pipeline.heuristics import MIN_CONTENT_CHARS
from pipeline.publishers import (
    PublisherResolver,
    feed_sources_from_db,
)
from pipeline.sources.ainews import fetch_ai_news
from pipeline.sources.extract_content import fetch_full_content
from pipeline.sources.hn import fetch_hn
from pipeline.sources.substack import fetch_feeds
from pipeline.types import FetchedArticle
from pipeline.utils import log


@dataclass(frozen=True)
class Source:
    """One channel to poll. ``label`` is the stats/health grouping key, not a
    publisher — "Feeds" and "Newsletter" each cover many publishers.

    ``fetcher`` returns ``(articles, errors)`` — ``errors`` maps a publisher
    name to a hard-failure message (e.g. a 403). ``publisher_names`` is the
    full set of publishers this source is expected to poll this run; it's
    only populated for "Feeds" (the one source that's actually an aggregate
    of many named publishers) so per-publisher health can be recorded for
    each of them, including ones that silently fetched nothing.
    """

    label: str
    fetcher: Callable[[], tuple[list[FetchedArticle], dict[str, str]]]
    publisher_names: tuple[str, ...] = ()


def build_sources(session: Session) -> list[Source]:
    """Assemble the run's sources.

    RSS/substack feeds, Hacker News and AI News are polled — "Feeds" covers
    every active publisher with an rss or substack link (DB-driven via
    ``feed_sources_from_db``). The IMAP/lab-watch channels (Newsletter, Lab
    Watch) are intentionally disabled: they fetch thin items and blow up the
    downstream LLM budget. HN items start thin too but the fetch step fills
    their content (and drops any it cannot), so they survive. AI News extracts
    its own content inline (see ``sources/ainews.py``), so it doesn't need the
    re-fetch path either.
    """
    feed_sources = feed_sources_from_db(session)
    return [
        Source(
            "Feeds",
            lambda: fetch_feeds(feed_sources),
            publisher_names=tuple(s["name"] for s in feed_sources),
        ),
        Source("Hacker News", lambda: (fetch_hn(), {})),
        Source("AI News", lambda: (fetch_ai_news(), {})),
    ]


def fetch_source(source: Source) -> tuple[list[FetchedArticle], dict[str, str]]:
    """Poll one source, exactly as it emitted its items.

    Content filling is a separate call (``fill_content``) so the agent's inbox
    can record what the source actually returned, thin items included, before
    the LLM funnel drops the ones it cannot work with.
    """
    articles, errors = source.fetcher()
    if not articles:
        log(f"No articles from {source.label}")
    return articles, errors


def fill_content(articles: list[FetchedArticle], label: str) -> list[FetchedArticle]:
    """Fill each item's content at fetch time, then drop the ones still empty.

    Feeds already carry ``content:encoded``; thin items (< ``MIN_CONTENT_CHARS``)
    get a network re-fetch — direct, then residential proxy — via
    ``fetch_full_content``. An article with no usable content after that is
    dropped and logged: the LLM steps assume full content, so a contentless
    item has nothing to categorize and no point being scored or inserted.

    Only the LLM funnel needs this. The agent's inbox is filled from the raw
    fetch and keeps the thin items.
    """
    if not articles:
        return articles
    thin = [a for a in articles if len(a.get("content") or "") < MIN_CONTENT_CHARS]
    if thin:
        content_map = fetch_full_content([a["url"] for a in thin])
        for a in thin:
            full = content_map.get(a["url"])
            if full:
                a["content"] = full

    kept = [a for a in articles if (a.get("content") or "").strip()]
    dropped = len(articles) - len(kept)
    if dropped:
        log(f"  {label}: dropped {dropped} article(s) with no content")
    return kept


def resolve_publishers(
    articles: list[FetchedArticle], resolver: PublisherResolver
) -> None:
    """Stamp each fetched item in place with publisher_id and trust.

    Both come from the Publisher row (resolved by source name, auto-quarantined
    if unknown). Runs right after fetch so trust is available to the
    scoring/dedup BAML calls.
    """
    for a in articles:
        publisher = resolver.resolve(a["source"])
        assert publisher.id is not None
        a["publisher_id"] = publisher.id
        a["trust"] = publisher.trust.value
