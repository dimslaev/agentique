"""Step 1: poll the sources, and resolve each item's publisher."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session

from app.platform.logging import log
from pipeline.heuristics import AI_TITLE_KEYWORDS, MIN_CONTENT_CHARS
from pipeline.publishers import (
    PublisherResolver,
    feed_sources_from_db,
    lab_watch_targets_from_db,
    newsletter_senders_from_db,
)
from pipeline.sources.ainews import fetch_ai_news
from pipeline.sources.email import fetch_newsletter
from pipeline.sources.extract_content import fetch_full_content
from pipeline.sources.hn import fetch_hn
from pipeline.sources.lab_watch import fetch_lab_watch
from pipeline.sources.reddit import fetch_reddit
from pipeline.sources.substack import fetch_feeds
from pipeline.types import FetchedArticle


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

    "Feeds" covers every active publisher with an rss or substack link
    (DB-driven via ``feed_sources_from_db``); "Lab Watch" covers the labs that
    publish no feed at all, discovered first-party via search (one Tavily call
    per target per run, DB-driven via ``lab_watch_targets_from_db``).

    Lab Watch was disabled for a while because its items arrive as a search
    snippet and the thin ones were reaching the scorer. That is a fetch
    problem, not a channel problem: ``_with_content`` re-fetches anything under
    ``MIN_CONTENT_CHARS`` and drops what stays thin, which is the same path
    that makes Hacker News (also thin at fetch) safe. So it is routed through
    it like every other source. AI News extracts its own content inline (see
    ``sources/ainews.py``), so it does not need the re-fetch path.

    Hacker News and Reddit are firehoses rather than publishers: both filter
    hard at the source (a keyword gate on HN, the subreddit itself on Reddit)
    and both arrive thin, so they lean on the re-fetch path too.

    "Newsletter" is the IMAP channel: unread mail in the "sub" mailbox matched
    against every active publisher with an ``email`` link (DB-driven via
    ``newsletter_senders_from_db``). An item is a product named in an issue,
    resolved to a first-party URL by search rather than by the mail's own
    tracking links, so it arrives carrying only the issue's blurb and leans on
    the re-fetch path like the other thin sources.
    """
    feed_sources = feed_sources_from_db(session)
    lab_watch_targets = lab_watch_targets_from_db(session)
    newsletter_senders = newsletter_senders_from_db(session)
    return [
        Source(
            "Feeds",
            lambda: fetch_feeds(feed_sources),
            publisher_names=tuple(s["name"] for s in feed_sources),
        ),
        Source("Hacker News", lambda: (fetch_hn(), {})),
        Source("Reddit", lambda: (fetch_reddit(), {})),
        Source("AI News", lambda: (fetch_ai_news(), {})),
        Source("Newsletter", lambda: (fetch_newsletter(newsletter_senders), {})),
        Source(
            "Lab Watch",
            lambda: (fetch_lab_watch(lab_watch_targets), {}),
            publisher_names=tuple(name for name, _ in lab_watch_targets),
        ),
    ]


def fetch_source(source: Source) -> tuple[list[FetchedArticle], dict[str, str]]:
    articles, errors = source.fetcher()
    if not articles:
        log(f"No articles from {source.label}")
        return articles, errors
    return _with_content(articles, source.label), errors


def _with_content(articles: list[FetchedArticle], label: str) -> list[FetchedArticle]:
    """Fill each item's content at fetch time, then drop the ones still empty.

    Feeds already carry ``content:encoded``; thin items (< ``MIN_CONTENT_CHARS``)
    get a network re-fetch — direct, then residential proxy — via
    ``fetch_full_content``. An article with no usable content after that is
    dropped and logged: downstream steps assume full content, so a contentless
    item has nothing to categorize and no point being scored or inserted.
    """
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
    """Stamp each fetched item in place with publisher_id, trust and topic_gated.

    All three come from the Publisher row (resolved by source name,
    auto-quarantined if unknown). Runs right after fetch so trust is available
    to the scoring/dedup BAML calls and ``topic_gated`` to ``drop_off_topic``.
    """
    for a in articles:
        publisher = resolver.resolve(a["source"])
        assert publisher.id is not None
        a["publisher_id"] = publisher.id
        a["trust"] = publisher.trust.value
        a["topic_gated"] = publisher.topic_gated


def drop_off_topic(articles: list[FetchedArticle], label: str) -> list[FetchedArticle]:
    """Drop off-topic items from publishers marked ``topic_gated``.

    Some feeds worth carrying are broad engineering blogs that happen to post
    about AI a few times a month (Stripe, Figma, Spotify). Without a gate every
    one of their release notes and hiring posts reaches the scorer, and the LLM
    bill scales with the feed, not with the signal. So a gated publisher's items
    must match ``AI_TITLE_KEYWORDS`` on the title alone.

    Title-only and deliberately early — before dedup's embeddings and before
    ``prefilter_keep_drop`` — so a rejected item costs one regex and nothing
    else. Publishers that are on-topic by definition (an AI lab's own blog) are
    left ungated and pass through untouched; the recall/precision trade-off is
    the same one documented on ``AI_TITLE_KEYWORDS`` itself.
    """
    kept = [
        a
        for a in articles
        if not a.get("topic_gated") or AI_TITLE_KEYWORDS.search(a["title"])
    ]
    dropped = len(articles) - len(kept)
    if dropped:
        log(f"  {label}: dropped {dropped} off-topic item(s) from gated publishers")
    return kept
