"""Tweet items: point each at the page it links to, or keep its full text.

Before this, every tweet arrived with only its feed blurb and was dropped as
too thin, so Aligned News (all tweet links) reached the agent as event pages
and nothing else.
"""

from __future__ import annotations

import pytest

from pipeline.fetching import tweets
from pipeline.steps import fetch as fetch_step

_TWEET_URL = "https://x.com/cantinasecurity/status/2078158487759290614"


def _item(url: str, content: str = "a blurb") -> dict:
    return {"title": "A title", "url": url, "content": content, "source": "Feeds"}


def _tweet(text: str, *links: str) -> dict:
    facets = [{"type": "url", "replacement": link} for link in links]
    return {"text": text, "raw_text": {"text": text, "facets": facets}}


def _stub(monkeypatch, tweet: dict | None) -> list[str]:
    asked: list[str] = []

    def fetch_tweet(status_id: str) -> dict | None:
        asked.append(status_id)
        return tweet

    monkeypatch.setattr(tweets, "_fetch_tweet", fetch_tweet)
    return asked


@pytest.mark.parametrize(
    "url, expected",
    [
        (_TWEET_URL, "2078158487759290614"),
        ("https://twitter.com/a/status/1?s=20", "1"),
        ("https://x.com/a/status/1/photo/1", "1"),
        ("https://x.com/cantinasecurity", None),
        ("https://example.com/a/status/1", None),
    ],
)
def test_tweet_id(url, expected):
    assert tweets.tweet_id(url) == expected


def test_a_tweet_that_links_out_becomes_that_link(monkeypatch):
    link = "https://cantina.review/cantina-agentic-5a0a34"
    _stub(monkeypatch, _tweet("Full story:", f"{_TWEET_URL}/photo/1", link))
    [item] = tweets.unwrap_tweets([_item(_TWEET_URL)])
    assert item["url"] == link
    assert item["content"] == ""


def test_a_tweet_with_no_link_keeps_its_full_text(monkeypatch):
    text = "A long thread opener. " * 20
    _stub(monkeypatch, _tweet(text))
    [item] = tweets.unwrap_tweets([_item(_TWEET_URL)])
    assert item["url"] == _TWEET_URL
    assert item["content"] == text


def test_a_tweet_fxtwitter_cannot_return_is_left_as_it_came(monkeypatch):
    _stub(monkeypatch, None)
    [item] = tweets.unwrap_tweets([_item(_TWEET_URL)])
    assert item == _item(_TWEET_URL)


def test_items_that_are_not_tweets_are_never_looked_up(monkeypatch):
    asked = _stub(monkeypatch, None)
    tweets.unwrap_tweets([_item("https://example.com/post")])
    assert asked == []


@pytest.mark.parametrize(
    "url",
    [
        "https://luma.com/horizonagentshack",
        "https://lu.ma/abc",
        "https://partiful.com/e/xyz",
        "https://www.eventbrite.com/e/123",
    ],
)
def test_event_pages_are_dropped(url):
    assert fetch_step._without_events([_item(url)], "Feeds") == []


def test_articles_are_not_event_pages():
    item = _item("https://cantina.review/post")
    assert fetch_step._without_events([item], "Feeds") == [item]
