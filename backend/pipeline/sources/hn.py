"""Hacker News source: polls the newstories/newest feed and applies the traction gate."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from pipeline.config import hn_grace_hours, hn_min_comments, hn_min_points
from pipeline.heuristics import AI_TITLE_KEYWORDS, is_first_party
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


def _age_hours(item: dict) -> float | None:
    """Hours since the story was posted, or None if it carries no timestamp."""
    posted = item.get("time")
    if not posted:
        return None
    return (datetime.now(UTC).timestamp() - float(posted)) / 3600


def _passes_topic_and_window(item: dict) -> bool:
    """Every ``_to_article`` gate except traction — the denominator the run log
    reports the traction gate against."""
    if not item or item.get("type") != "story" or not item.get("title"):
        return False
    if not AI_TITLE_KEYWORDS.search(item["title"]):
        return False
    posted = item.get("time")
    pub_date = datetime.fromtimestamp(posted, tz=UTC).isoformat() if posted else None
    return is_within_window(pub_date)


def has_traction(item: dict) -> bool:
    """Has HN itself said this story is worth reading?

    The firehose is not an editorial feed — ``newstories`` is every submission,
    so a two-star repo posted by its author sits there next to a frontier
    release, and both look identical from title and URL alone. Points and
    comments are HN's own verdict on which is which, they ride along in the item
    JSON we already fetch, and until now the pipeline threw them away.

    Three cases:

    * **First-party lab post** — through regardless. A release on openai.com is
      news at zero points, and the whole reason ``newstories`` is polled is to
      catch it in the minutes before it trends.
    * **Still young** (under ``hn_grace_hours``) — no verdict yet. Every story
      starts at 1 point, so a vote count here means nothing either way, and this
      returns False to *hold the story back rather than reject it*: nothing
      dropped in a source is written to ``ScoredUrl``, so the next run re-reads
      the same id with settled numbers, still inside the 48h recency window.
      The cost is up to a day of latency on a non-lab story; the alternative is
      admitting the entire firehose blind, which is what filled the feed with
      noise.
    * **Aged out** — judged on ``hn_min_points`` upvotes or ``hn_min_comments``
      comments, either bar. A story that has been up half a day with neither is
      one nobody read, and that is the signal, not a proxy for it.

    Set ``HN_MIN_POINTS=0`` to turn the gate off entirely.
    """
    if hn_min_points() <= 0:
        return True
    if is_first_party(item.get("url") or ""):
        return True

    age = _age_hours(item)
    if age is not None and age < hn_grace_hours():
        return False

    points = item.get("score") or 0
    comments = item.get("descendants") or 0
    return points >= hn_min_points() or comments >= hn_min_comments()


def _to_article(item: dict) -> FetchedArticle | None:
    """One HN item -> a fetched article, or None if it fails a gate.

    Gates, cheapest first: it must be a titled story, its title must look
    AI-related, it must fall inside the pipeline's recency window, and HN's own
    readers must have given it some traction. Content stays empty here —
    ``extract_content`` fills it for the survivors.
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
    if not has_traction(item):
        return None
    points = item.get("score") or 0
    comments = item.get("descendants") or 0
    return {
        "title": clean_title(item["title"]),
        "url": item.get("url") or f"https://news.ycombinator.com/item?id={item['id']}",
        "content": "",
        "published_date": pub_date or datetime.now(UTC).isoformat(),
        "source": "Hacker News",
        # Carried to the scorer, not just used as a gate: told that a submission
        # is a Show HN sitting at 3 points, the model stops reading its title as
        # if it were an announcement.
        "traction": f"{points} points, {comments} comments on Hacker News",
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
    on_topic = 0
    for item in results:
        item = item or {}
        # Counted before the traction gate only, so the log separates "HN had
        # nothing about AI today" from "it did, and none of it had been read".
        if _passes_topic_and_window(item):
            on_topic += 1
        article = _to_article(item)
        if article is None or article["url"] in seen_urls:
            continue
        seen_urls.add(article["url"])
        articles.append(article)

    log(
        f"Hacker News: {len(articles)} of {on_topic} AI-related stories have "
        f"traction (>={hn_min_points()} points or >={hn_min_comments()} comments "
        f"after {hn_grace_hours():g}h); {len(ids)} ids scanned"
    )
    return extract_content(articles)
