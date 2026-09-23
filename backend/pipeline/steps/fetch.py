"""Step 1: poll the sources, and resolve each item's publisher."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session

from app.platform.logging import log
from pipeline.fetching.extract_content import fetch_full_content
from pipeline.publishers import (
    PublisherResolver,
    feed_sources_from_db,
    lab_watch_targets_from_db,
    newsletter_senders_from_db,
)
from pipeline.sources.email import fetch_newsletter
from pipeline.sources.hn import fetch_hn
from pipeline.sources.lab_watch import fetch_lab_watch
from pipeline.sources.substack import fetch_feeds
from pipeline.types import Candidate, RawItem

# Below this, content is a teaser/blurb rather than an article, and the
# categorizer fails on it ~30-40% of the time (vs ~2% above it). Used to decide
# whether a fetched item still needs a network re-fetch of its full text.
MIN_CONTENT_CHARS = 500

# Below this, even after the re-fetch, what is left is a teaser (a launch
# tweet, a one-line search snippet): too little to summarize without
# inventing, and an article is never inserted without a summary. Dropped here
# so it does not cost a scoring call first.
MIN_SUMMARIZABLE_CHARS = 300


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
    fetcher: Callable[[], tuple[list[RawItem], dict[str, str]]]
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
    it like every other source.

    Hacker News is a firehose rather than a publisher: it filters hard at the
    source (a keyword gate) and arrives thin, so it leans on the re-fetch path
    too. Reddit and AI News were dropped on 2026-09-23 after a week of fetching
    nothing.

    "Newsletter" is the IMAP channel: unread mail in the "sub" mailbox matched
    against every active publisher with an ``email`` link (DB-driven via
    ``newsletter_senders_from_db``). An item is a link in an issue that Jev
    classified as on-topic editorial, resolved to its destination (or, for a
    product linked off its maker's site, to a first-party URL by search). It
    arrives with no content and leans on the re-fetch path like the other thin
    sources.
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
        Source("Newsletter", lambda: (fetch_newsletter(newsletter_senders), {})),
        Source(
            "Lab Watch",
            lambda: (fetch_lab_watch(lab_watch_targets), {}),
            publisher_names=tuple(name for name, _ in lab_watch_targets),
        ),
    ]


def fetch_source(source: Source) -> tuple[list[RawItem], dict[str, str]]:
    articles, errors = source.fetcher()
    if not articles:
        log(f"No articles from {source.label}")
        return articles, errors
    return _with_content(articles, source.label), errors


def _with_content(articles: list[RawItem], label: str) -> list[RawItem]:
    """Fill each item's content at fetch time, then drop the ones still thin.

    Feeds already carry ``content:encoded``; thin items (< ``MIN_CONTENT_CHARS``)
    get a network re-fetch — direct, then residential proxy — via
    ``fetch_full_content``. An article still under ``MIN_SUMMARIZABLE_CHARS``
    after that is dropped and logged: it has nothing to summarize, so it has no
    point being scored or inserted.
    """
    thin = [a for a in articles if len(a["content"]) < MIN_CONTENT_CHARS]
    if thin:
        pages = fetch_full_content([a["url"] for a in thin])
        for a in thin:
            page = pages.get(a["url"])
            if page:
                a["content"] = page.text
                a["links"] = page.links

    kept = [a for a in articles if len(a["content"].strip()) >= MIN_SUMMARIZABLE_CHARS]
    dropped = len(articles) - len(kept)
    if dropped:
        log(f"  {label}: dropped {dropped} article(s) with too little content")
    return kept


def resolve_publishers(
    articles: list[RawItem], resolver: PublisherResolver
) -> list[Candidate]:
    """Turn fetched items into candidates by resolving each one's publisher.

    publisher_id, trust and publisher_kind come from the Publisher row: the
    one whose site the URL is on when we know it, else the one named by the
    source (auto-quarantined if unknown).

    Crediting by URL first is what lets an individual's post found through
    Hacker News or a newsletter count as theirs. ``source`` is left alone: it
    is still where we found the item, which traction and the run stats read.

    Returns new dicts rather than stamping the fetched ones in place: it is the
    only producer of ``Candidate``, which is what lets every step below it read
    those keys without a default.
    """
    candidates: list[Candidate] = []
    for a in articles:
        publisher = resolver.credit(a["url"]) or resolver.resolve(a["source"])
        assert publisher.id is not None
        candidates.append(
            {
                **a,
                "publisher_id": publisher.id,
                "trust": publisher.trust.value,
                "publisher_kind": publisher.kind.value,
            }
        )
    return candidates
