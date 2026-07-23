"""Stage 1: poll every active RSS/substack feed and build PipelineArticles.

Feeds are fetched in parallel; one bad feed logs and yields nothing rather than
sinking the batch. Each feed is tried direct first and, only if it comes back
blocked (403/429), retried through the residential proxy. Every entry's body is
run through the same trafilatura pass the article re-fetch uses, so thin
teasers are recorded as empty content here and picked up by the enrich stage.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser

from pipeline_new import http
from pipeline_new.config import residential_proxy_url
from pipeline_new.content import extract_text
from pipeline_new.text import clean_title
from pipeline_new.types import FeedPublisher, PipelineArticle
from pipeline_new.util import is_within_window, log

FEED_TIMEOUT_RETRIES = 2
FEED_BACKOFF_SECS = 2.0
FETCH_CONCURRENCY = 10


def _entry_content(entry) -> str:
    """Sanitized plain text for a feed entry, preferring the full
    ``content:encoded`` over the shorter ``summary`` teaser. Both carry HTML, so
    both go through ``extract_text`` — a teaser too thin to be an article
    resolves to "" and the enrich stage will re-fetch the page."""
    encoded = max(
        ((c.get("value") or "") for c in (entry.get("content") or [])),
        key=len,
        default="",
    )
    return extract_text(encoded or entry.get("summary") or "")


def _fetch_feed_xml(rss_url: str) -> str:
    """Feed XML, retrying through the proxy on a block. A non-block failure is
    raised immediately — retrying a 404 or a DNS error wastes a proxy hop."""
    proxy = residential_proxy_url()
    for attempt in range(FEED_TIMEOUT_RETRIES + 1):
        use_proxy = attempt > 0 and bool(proxy)
        try:
            resp = http.get(rss_url, proxy=proxy if use_proxy else None)
        except Exception as e:
            raise RuntimeError(f"fetch failed{' (proxy)' if use_proxy else ''}: {e}") from e

        if resp.is_success:
            return resp.text
        if resp.status_code in (403, 429) and attempt < FEED_TIMEOUT_RETRIES and proxy:
            time.sleep(FEED_BACKOFF_SECS * (2**attempt))
            continue
        raise RuntimeError(f"status {resp.status_code}")

    raise RuntimeError("exhausted retries")


def _fetch_one(pub: FeedPublisher) -> list[PipelineArticle]:
    log(f"Fetching {pub.name}...")
    try:
        feed = feedparser.parse(_fetch_feed_xml(pub.rss_url))
    except Exception as e:
        log(f"  FAILED {pub.name}: {e}")
        return []

    entries = feed.get("entries", [])
    if not entries:
        log(f"  {pub.name}: feed parsed but has no entries — check the URL")
        return []

    articles: list[PipelineArticle] = []
    for it in entries:
        published = it.get("published") or it.get("updated") or ""
        if not is_within_window(published):
            continue
        url = it.get("link") or ""
        title = clean_title(it.get("title") or "")
        if not url or not title:
            continue
        articles.append(
            PipelineArticle(
                url=url,
                title=title,
                content=_entry_content(it),
                published_date=published,
                publisher_id=pub.id,
                source=pub.name,
                trust=pub.trust,
            )
        )
    log(f"  {pub.name}: {len(articles)} in window")
    return articles


def _dedupe_by_url(articles: list[PipelineArticle]) -> list[PipelineArticle]:
    """One article per URL within this batch (two feeds can carry the same
    link), keeping the first — order is otherwise irrelevant this early."""
    seen: dict[str, PipelineArticle] = {}
    for a in articles:
        seen.setdefault(a.url, a)
    return list(seen.values())


def fetch_all(publishers: list[FeedPublisher]) -> list[PipelineArticle]:
    if not publishers:
        log("No active feed publishers")
        return []

    articles: list[PipelineArticle] = []
    with ThreadPoolExecutor(max_workers=FETCH_CONCURRENCY) as executor:
        futures = [executor.submit(_fetch_one, p) for p in publishers]
        for future in as_completed(futures):
            try:
                articles.extend(future.result())
            except Exception:
                pass

    deduped = _dedupe_by_url(articles)
    log(f"Fetched {len(deduped)} unique articles from {len(publishers)} feeds")
    return deduped
