from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from pipeline.heuristics import AI_TITLE_KEYWORDS
from pipeline.sources.extract_content import extract_content
from pipeline.sources.http import fetch_with_timeout
from pipeline.types import FetchedArticle
from pipeline.utils import clean_title, is_within_window, log

HN_ITEM = "https://hacker-news.firebaseio.com/v0/item"

# Two firehoses, both title-gated by AI_TITLE_KEYWORDS before any item is
# fetched in full. "top" is the front page — high signal, but an AI post only
# reaches it if it already trended. "new" is every submission in publication
# order, which is where a lab's own release lands minutes after it goes up and
# often never climbs any higher. Together they roughly double HN reach for the
# cost of a few hundred extra id lookups (a JSON blob each, no LLM involved).
HN_FEEDS = (
    ("top", "https://hacker-news.firebaseio.com/v0/topstories.json"),
    ("new", "https://hacker-news.firebaseio.com/v0/newstories.json"),
)
HN_FETCH_LIMIT = 200


def _fetch_item(item_id: int) -> dict | None:
    try:
        resp = fetch_with_timeout(f"{HN_ITEM}/{item_id}.json", timeout=10.0)
        return resp.json()
    except Exception:
        return None


def _story_ids(label: str, url: str) -> list[int]:
    try:
        resp = fetch_with_timeout(url)
        ids: list[int] = resp.json()
    except Exception as e:
        log(f"  HN {label} stories fetch failed: {e}")
        return []
    return ids[:HN_FETCH_LIMIT]


def _to_article(item: dict) -> FetchedArticle | None:
    """One HN item -> a fetched article, or None if it fails a gate.

    Gates, cheapest first: it must be a titled story, its title must look
    AI-related, and it must fall inside the pipeline's recency window. Content
    stays empty here — ``extract_content`` fills it for the survivors.
    """
    if not item or item.get("type") != "story" or not item.get("title"):
        return None
    if not AI_TITLE_KEYWORDS.search(item["title"]):
        return None
    pub_date = (
        datetime.fromtimestamp(item["time"], tz=UTC).isoformat()
        if item.get("time")
        else None
    )
    if not is_within_window(pub_date):
        return None
    return {
        "title": clean_title(item["title"]),
        "url": item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}",
        "content": "",
        "published_date": pub_date or datetime.now(UTC).isoformat(),
        "source": "Hacker News",
    }


def fetch_hn() -> list[FetchedArticle]:
    log("Fetching Hacker News top + new stories...")

    # The two lists overlap heavily (a new story that trends is on both), so
    # dedupe ids before spending a lookup on them.
    seen_ids: set[int] = set()
    ids: list[int] = []
    for label, url in HN_FEEDS:
        for item_id in _story_ids(label, url):
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                ids.append(item_id)

    if not ids:
        return []

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(_fetch_item, ids))

    seen_urls: set[str] = set()
    articles: list[FetchedArticle] = []
    for item in results:
        article = _to_article(item or {})
        if article is None or article["url"] in seen_urls:
            continue
        seen_urls.add(article["url"])
        articles.append(article)

    log(f"Hacker News: {len(articles)} AI-related stories from {len(ids)} ids")
    return extract_content(articles)
