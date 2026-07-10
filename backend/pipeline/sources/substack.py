from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser
import httpx

from pipeline.sources.utils import BROWSER_HEADERS, clean_title, is_within_window
from pipeline.utils import log

_PROXY_URL = os.environ.get("RESIDENTIAL_PROXY_URL")

if _PROXY_URL:
    try:
        from urllib.parse import urlparse

        _u = urlparse(_PROXY_URL)
        log(
            f"Substack proxy: {_u.scheme}://{_u.hostname}:{_u.port or '(default)'} (auth: {'yes' if _u.username else 'no'})"
        )
    except Exception:
        log(f"Substack proxy: set but unparseable (len {len(_PROXY_URL)})")
else:
    log("Substack proxy: none (RESIDENTIAL_PROXY_URL unset)")


def _fetch_feed_xml(url: str, retries: int = 2, backoff: float = 2.0) -> str:
    for attempt in range(retries + 1):
        use_proxy = attempt > 0 and bool(_PROXY_URL)
        kwargs: dict = {
            "headers": BROWSER_HEADERS,
            "timeout": 15.0,
            "follow_redirects": True,
        }
        if use_proxy:
            kwargs["proxy"] = _PROXY_URL
        try:
            with httpx.Client(**kwargs) as client:
                resp = client.get(url)
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


def _fetch_source(source: dict) -> list[dict]:
    name = source["name"]
    rss_url = source["rssUrl"]
    log(f"Fetching {name}...")
    try:
        xml = _fetch_feed_xml(rss_url)
        feed = feedparser.parse(xml)
        items = feed.get("entries", [])
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
                "content": it.get("summary") or "",
                "published_date": it.get("published") or it.get("updated") or "",
                "source": name,
                "source_type": "rss",
            }
            for it in within
        ]
    except Exception as e:
        log(f"  FAILED {name}: {e}")
        return []


def fetch_feeds(sources: list[dict]) -> list[dict]:
    """Fetch a list of RSS/substack feeds in parallel.

    ``sources`` is ``[{"name": ..., "rssUrl": ...}]`` — the runtime builds it
    from the DB (active publishers with rss/substack links) via
    ``pipeline.publishers.feed_sources_from_db``. All items are stamped
    ``source_type="rss"``; the caller resolves each ``source`` name to a
    Publisher row.
    """
    if not sources:
        log("Feeds: no active feed publishers")
        return []

    articles: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_source, src): src for src in sources}
        for future in as_completed(futures):
            try:
                articles.extend(future.result())
            except Exception:
                pass

    log(f"Feeds: {len(articles)} articles")
    return articles
