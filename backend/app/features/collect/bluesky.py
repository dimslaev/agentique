"""Bluesky source: the links posted by the people agentique's own account follows.

Who the pipeline reads is changed by following or unfollowing in the Bluesky
app, not in the publishers table. Follows and author feeds are public (no
login), unlike post search, which needs an account. A post becomes one item per link
it makes. A post with no link has no article to judge and is skipped, and so
is any post whose text names nothing on the HN topic map, because builders
post about everything.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict
from urllib.parse import urlencode

from app.core.http import fetch_with_timeout
from app.core.logging import log
from app.core.urls import hostname
from app.features.collect.freshness import is_within_window
from app.features.collect.hn import is_on_topic
from app.features.collect.model import RawItem
from app.features.collect.titles import clean_title

API = "https://public.api.bsky.app/xrpc"
FOLLOWS_PAGE = 100
FOLLOWS_MAX_PAGES = 10
# Posts read per followed author. Newest first, so 30 covers the 48h window
# for anyone who is not a firehose.
AUTHOR_POSTS = 30
CONCURRENCY = 5
# Bluesky itself, and pages that only discuss a story: the story is queued from
# its own link, so these would queue it a second time under another URL.
SKIP_HOSTS = {
    "bsky.app",
    "bsky.social",
    "techmeme.com",
    "news.ycombinator.com",
    "app.hncompanion.com",
}

# The slice of the app.bsky.feed.defs#postView JSON this module reads.
Feature = TypedDict("Feature", {"$type": str, "uri": str}, total=False)


class Facet(TypedDict, total=False):
    features: list[Feature]


class Record(TypedDict, total=False):
    text: str
    createdAt: str
    facets: list[Facet]


class Card(TypedDict, total=False):
    uri: str
    title: str
    description: str


class Embed(TypedDict, total=False):
    external: Card


class Author(TypedDict):
    handle: str


class Post(TypedDict, total=False):
    author: Author
    record: Record
    embed: Embed
    likeCount: int
    repostCount: int


class Entry(TypedDict):
    post: Post


class Follow(TypedDict):
    did: str


class Page(TypedDict, total=False):
    feed: list[Entry]
    follows: list[Follow]
    cursor: str


def bluesky_handle() -> str:
    """The account whose follows are read."""
    return os.environ.get("BLUESKY_HANDLE", "agentique.ch")


def _get(method: str, **params: str | int) -> Page:
    resp = fetch_with_timeout(f"{API}/{method}?{urlencode(params)}")
    resp.raise_for_status()  # a rate limit must not read as an empty feed
    page: Page = resp.json()
    return page


def _links(post: Post) -> list[str]:
    """The post's outbound links: the link card first, then links in the text."""
    urls: list[str] = []
    card: Card = post.get("embed", {}).get("external", {})
    if card.get("uri"):
        urls.append(card["uri"])
    for facet in post["record"].get("facets", []):
        for feature in facet.get("features", []):
            if feature.get("$type") == "app.bsky.richtext.facet#link":
                urls.append(feature.get("uri", ""))
    return [
        u
        for u in dict.fromkeys(urls)
        if u.startswith("http") and hostname(u) not in SKIP_HOSTS
    ]


def to_items(post: Post) -> list[RawItem]:
    record = post["record"]
    text = record.get("text") or ""
    card: Card = post.get("embed", {}).get("external", {})
    if not is_on_topic(f"{card.get('title', '')} {card.get('description', '')} {text}"):
        return []
    published = record.get("createdAt")
    if not is_within_window(published):
        return []
    traction = (
        f"{post.get('likeCount') or 0} likes, {post.get('repostCount') or 0} reposts"
        f" on Bluesky, posted by @{post['author']['handle']}: {text[:300]}"
    )
    return [
        {
            "title": clean_title(
                card["title"]
                if url == card.get("uri") and card.get("title")
                else text.split("\n")[0][:200]
            ),
            "url": url,
            "content": "",
            "published_date": published,
            "source": "Bluesky",
            "traction": traction,
        }
        for url in _links(post)
    ]


def _follows(handle: str) -> list[str]:
    dids: list[str] = []
    cursor = ""
    for _ in range(FOLLOWS_MAX_PAGES):
        page = _get(
            "app.bsky.graph.getFollows",
            actor=handle,
            limit=FOLLOWS_PAGE,
            **({"cursor": cursor} if cursor else {}),
        )
        dids += [f["did"] for f in page.get("follows", [])]
        cursor = page.get("cursor", "")
        if not cursor:
            break
    return dids


def _author_items(did: str) -> list[RawItem]:
    """One author's recent link posts. A failed author is skipped, not the run."""
    try:
        page = _get(
            "app.bsky.feed.getAuthorFeed",
            actor=did,
            limit=AUTHOR_POSTS,
            filter="posts_no_replies",
        )
    except Exception as e:
        log(f"  Bluesky {did} failed: {e}")
        return []
    return [item for entry in page.get("feed", []) for item in to_items(entry["post"])]


def fetch_bluesky(handle: str) -> list[RawItem]:
    log(f"Fetching Bluesky posts from the accounts {handle} follows...")
    dids = _follows(handle)
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        results = list(executor.map(_author_items, dids))
    items: dict[str, RawItem] = {}
    for found in results:
        for item in found:
            items.setdefault(item["url"], item)
    log(f"Bluesky: {len(items)} links from {len(dids)} followed accounts")
    return list(items.values())
