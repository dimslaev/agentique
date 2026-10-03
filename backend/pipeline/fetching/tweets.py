"""Turn a tweet item into the page the tweet points at, via the fxtwitter API.

x.com shows a login wall to anything that is not a signed-in browser, so
``extract_content`` skips it and a tweet arrives with only its feed blurb,
which the fetch step then drops as too thin. Aligned News is nothing but tweet
links; Hacker News and the newsletters carry some too.

fxtwitter is a free public mirror that returns a tweet as JSON, with every
t.co link already resolved. A tweet that links out becomes that link, so the
item is credited, fetched and judged as the article itself. A tweet with no
link keeps its own full text as content. When fxtwitter is down the item is
left as it came, which is what happened to every tweet before this.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict
from urllib.parse import urlparse

from app.platform.logging import log
from pipeline.fetching.http import fetch_with_timeout
from pipeline.types import RawItem
from pipeline.urls import hostname

FXTWITTER_URL = "https://api.fxtwitter.com/status/{id}"
TIMEOUT_SECS = 5.0
CONCURRENCY = 5
# fxtwitter sits behind a bot challenge that turns away httpx's default agent.
HEADERS = {"User-Agent": "agentique (+https://agentique.ch)"}

_TWEET_HOSTS = {"x.com", "twitter.com", "mobile.twitter.com"}
_STATUS_PATH = re.compile(r"^/[^/]+/status/(\d+)")


class _Facet(TypedDict, total=False):
    type: str
    replacement: str


class _RawText(TypedDict, total=False):
    facets: list[_Facet]


class Tweet(TypedDict, total=False):
    """The slice of fxtwitter's ``tweet`` object this module reads."""

    text: str
    raw_text: _RawText


def tweet_id(url: str) -> str | None:
    if hostname(url) not in _TWEET_HOSTS:
        return None
    match = _STATUS_PATH.match(urlparse(url).path)
    return match.group(1) if match else None


def _fetch_tweet(status_id: str) -> Tweet | None:
    try:
        resp = fetch_with_timeout(
            FXTWITTER_URL.format(id=status_id), timeout=TIMEOUT_SECS, headers=HEADERS
        )
        if not resp.is_success:
            return None
        tweet: Tweet | None = resp.json().get("tweet")
        return tweet
    except Exception:
        return None


def _outbound_link(tweet: Tweet) -> str | None:
    """The first link in the tweet that leaves x.com (a photo link does not)."""
    for facet in (tweet.get("raw_text") or {}).get("facets") or []:
        url = facet.get("replacement") if facet.get("type") == "url" else None
        if url and hostname(url) not in _TWEET_HOSTS:
            return url
    return None


def unwrap_tweets(articles: list[RawItem]) -> list[RawItem]:
    """Point each tweet item at the page it links to, in place."""
    ids = {a["url"]: tid for a in articles if (tid := tweet_id(a["url"]))}
    if not ids:
        return articles
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        tweets = dict(zip(ids, pool.map(_fetch_tweet, ids.values()), strict=True))

    unwrapped = 0
    for a in articles:
        tweet = tweets.get(a["url"])
        if not tweet:
            continue
        link = _outbound_link(tweet)
        if link:
            # Empty so the fetch step reads the destination; the tweet's blurb
            # is not the article.
            a["url"], a["content"] = link, ""
            unwrapped += 1
        elif len(tweet.get("text") or "") > len(a["content"]):
            a["content"] = tweet["text"]
    log(f"  tweets: {unwrapped} of {len(ids)} pointed at the page they link to")
    return articles
