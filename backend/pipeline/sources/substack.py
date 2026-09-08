"""Fetches recent posts from the curated list of Substack newsletters."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import feedparser

from app.platform.logging import log
from pipeline.fetching.extract_content import extract_text
from pipeline.fetching.http import (
    BROWSER_HEADERS,
    RESIDENTIAL_PROXY_URL,
    fetch_with_timeout,
)
from pipeline.freshness import is_within_window
from pipeline.titles import clean_title
from pipeline.types import RawItem
from pipeline.urls import feed_url

_PROXY_URL = RESIDENTIAL_PROXY_URL
_proxy_status_logged = False


def _log_proxy_status_once() -> None:
    """Diagnostic, logged the first time a feed is actually fetched — not at
    import, so importing this module (tests included) has no side effect."""
    global _proxy_status_logged
    if _proxy_status_logged:
        return
    _proxy_status_logged = True

    if not _PROXY_URL:
        log("Substack proxy: none (RESIDENTIAL_PROXY_URL unset)")
        return
    try:
        u = urlparse(_PROXY_URL)
        log(
            f"Substack proxy: {u.scheme}://{u.hostname}:{u.port or '(default)'} "
            f"(auth: {'yes' if u.username else 'no'})"
        )
    except Exception:
        log(f"Substack proxy: set but unparseable (len {len(_PROXY_URL)})")


def _entry_content(entry) -> str:
    """Plain text for a feed entry, preferring ``content:encoded`` over the
    ``summary`` teaser.

    Both fields carry HTML, so they go through the same trafilatura pass the
    network extractor uses — that keeps the text comparable and lets
    ``_is_blocker`` reject teasers (anything under 50 chars) as empty rather
    than passing a blurb off as an article.
    """
    encoded = max(
        ((c.get("value") or "") for c in (entry.get("content") or [])),
        key=len,
        default="",
    )
    return extract_text(encoded or entry.get("summary") or "")


def _fetch_feed_xml(url: str, retries: int = 2, backoff: float = 2.0) -> str:
    for attempt in range(retries + 1):
        use_proxy = attempt > 0 and bool(_PROXY_URL)
        try:
            resp = fetch_with_timeout(
                url,
                timeout=15.0,
                proxy=_PROXY_URL if use_proxy else None,
                headers=BROWSER_HEADERS,
            )
        except Exception as e:
            raise RuntimeError(
                f"fetch failed{'(via proxy)' if use_proxy else ''}: {e}"
            ) from e

        if resp.is_success:
            return resp.text
        if resp.status_code in (403, 429) and attempt < retries and _PROXY_URL:
            time.sleep(backoff * (2**attempt))
            continue
        raise RuntimeError(f"Status code {resp.status_code}")

    raise RuntimeError("Exhausted retries")


def _fetch_source(source: dict) -> tuple[list[RawItem], str | None]:
    name = source["name"]
    rss_url = source["rssUrl"]
    log(f"Fetching {name}...")
    try:
        xml = _fetch_feed_xml(feed_url(rss_url))
        feed = feedparser.parse(xml)
        items = feed.get("entries", [])
        if not items:
            log(f"  {name}: feed parsed but has no entries — check the feed URL")
        within = [
            it
            for it in items
            if is_within_window(it.get("published") or it.get("updated"))
        ]
        log(f"  {name}: {len(within)} in window")
        return [
            {
                "title": clean_title(it.get("title") or "(no title)"),
                "url": it.get("link") or "",
                "content": _entry_content(it),
                "published_date": it.get("published") or it.get("updated") or "",
                "source": name,
            }
            for it in within
        ], None
    except Exception as e:
        log(f"  FAILED {name}: {e}")
        return [], f"{type(e).__name__}: {e}"


def fetch_feeds(sources: list[dict]) -> tuple[list[RawItem], dict[str, str]]:
    """Fetch a list of RSS/substack feeds in parallel.

    ``sources`` is ``[{"name": ..., "rssUrl": ...}]`` — the runtime builds it
    from the DB (active publishers with rss/substack links) via
    ``pipeline.publishers.feed_sources_from_db``. The caller resolves each
    ``source`` name to a Publisher row.

    Returns ``(articles, errors)`` where ``errors`` maps a feed's ``name`` to
    the exception message for any feed that failed outright (e.g. a 403) —
    this is what lets per-publisher health tell "that feed is broken" apart
    from "that feed just had nothing new".
    """
    if not sources:
        log("Feeds: no active feed publishers")
        return [], {}

    _log_proxy_status_once()

    articles: list[RawItem] = []
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_source, src): src for src in sources}
        for future in as_completed(futures):
            name = futures[future]["name"]
            try:
                items, error = future.result()
                articles.extend(items)
                if error:
                    errors[name] = error
            except Exception as e:
                errors[name] = f"{type(e).__name__}: {e}"

    log(f"Feeds: {len(articles)} articles")
    return articles, errors
