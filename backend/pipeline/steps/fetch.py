"""Step 1: poll the sources, and resolve each item's publisher."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session

from pipeline.publishers import (
    PublisherResolver,
    feed_sources_from_db,
    lab_watch_targets_from_db,
    newsletter_senders_from_db,
)
from pipeline.sources.ainews import fetch_ai_news
from pipeline.sources.email import fetch_newsletter
from pipeline.sources.hn import fetch_hn
from pipeline.sources.lab_watch import fetch_lab_watch
from pipeline.sources.substack import fetch_feeds
from pipeline.types import FetchedArticle
from pipeline.utils import log


@dataclass(frozen=True)
class Source:
    """One channel to poll. ``label`` is the stats/health grouping key, not a
    publisher — "Feeds" and "Newsletter" each cover many publishers."""

    label: str
    fetcher: Callable[[], list[FetchedArticle]]


def build_sources(session: Session) -> list[Source]:
    """Assemble the run's sources. Aggregator channels (HN, AI News) keep their
    fetchers; RSS/substack feeds and IMAP newsletter senders are both DB-driven
    — "Feeds" polls every active feed publisher, "Newsletter" matches unread
    mail against every active publisher with an ``email`` link.
    """
    return [
        Source("Hacker News", fetch_hn),
        Source(
            "Newsletter",
            lambda: fetch_newsletter(newsletter_senders_from_db(session)),
        ),
        Source("AI News", fetch_ai_news),
        Source("Feeds", lambda: fetch_feeds(feed_sources_from_db(session))),
        Source(
            "Lab Watch",
            lambda: fetch_lab_watch(lab_watch_targets_from_db(session)),
        ),
    ]


def fetch_source(source: Source) -> list[FetchedArticle]:
    articles = source.fetcher()
    if not articles:
        log(f"No articles from {source.label}")
    return articles


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
