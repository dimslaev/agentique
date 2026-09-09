"""The Reddit source's post -> article conversion, and the cross-subreddit dedupe.

Reddit hands back a mix of link posts (the interesting case — they point
somewhere with real text) and self posts (the body is the content), plus a lot
that is neither: stickied announcements, image dumps, low-score help threads.
Which of those becomes an article is the decision worth pinning.
"""

from __future__ import annotations

import time

import pytest

from pipeline.sources import reddit
from pipeline.sources.reddit import MIN_SCORE, _to_article


def _post(**overrides) -> dict:
    """A listing entry's ``data`` object, defaulted to a passing link post."""
    return {
        "title": "Qwen3-Max weights are up",
        "url": "https://example.com/qwen3",
        "permalink": "/r/LocalLLaMA/comments/abc/qwen3/",
        "score": MIN_SCORE + 100,
        "created_utc": time.time(),
        "is_self": False,
        "stickied": False,
        "over_18": False,
        **overrides,
    }


# ─── _to_article ─────────────────────────────────────────────────────────────


def test_link_post_takes_the_linked_url_not_the_permalink():
    """The article is what the post points at — the reddit thread is just the
    pointer, and scoring the thread instead would lose the actual content."""
    article = _to_article(_post())
    assert article is not None
    assert article["url"] == "https://example.com/qwen3"
    assert article["content"] == ""
    assert article["source"] == "Reddit"


def test_self_post_takes_its_permalink_and_body():
    article = _to_article(
        _post(is_self=True, url=None, selftext="  Benchmarks inside.  ")
    )
    assert article is not None
    assert article["url"].endswith("/r/LocalLLaMA/comments/abc/qwen3/")
    assert article["content"] == "Benchmarks inside."


@pytest.mark.parametrize(
    "override, why",
    [
        ({"title": ""}, "no title"),
        ({"stickied": True}, "a pinned mod post, not news"),
        ({"over_18": True}, "NSFW"),
        ({"removed_by_category": "moderator"}, "removed by a mod"),
        ({"score": MIN_SCORE - 1}, "below the upvote floor"),
        ({"created_utc": time.time() - 60 * 60 * 24 * 30}, "outside the window"),
        ({"url": ""}, "a link post with no link"),
        ({"url": "https://i.redd.it/abc.png"}, "an image, nothing to extract"),
        ({"url": "https://v.redd.it/abc"}, "a clip, nothing to extract"),
        ({"url": "https://www.youtube.com/watch?v=x"}, "a video, nothing to extract"),
    ],
)
def test_rejects(override, why):
    assert _to_article(_post(**override)) is None, why


def test_a_score_at_the_floor_is_kept():
    assert _to_article(_post(score=MIN_SCORE)) is not None


def test_a_post_with_no_score_field_is_treated_as_zero():
    assert _to_article(_post(score=None)) is None


def test_a_post_with_no_timestamp_is_kept():
    """is_within_window keeps an undated item on purpose; a listing entry
    missing created_utc is an API oddity, not a reason to drop the release."""
    article = _to_article(_post(created_utc=None))
    assert article is not None
    assert article["published_date"]


def test_media_host_check_ignores_a_www_prefix():
    assert _to_article(_post(url="https://www.imgur.com/a/x")) is None


def test_a_self_post_on_a_media_host_url_is_still_kept():
    """is_self short-circuits the link checks — the body is the content, and
    the url field on a self post is just the permalink again."""
    article = _to_article(
        _post(is_self=True, url="https://i.redd.it/x.png", selftext="Long writeup")
    )
    assert article is not None
    assert article["content"] == "Long writeup"


# ─── fetch_reddit ────────────────────────────────────────────────────────────


def _stub_reddit(monkeypatch, posts_by_sub: dict[str, list[dict]]) -> None:
    monkeypatch.setattr(
        reddit,
        "_fetch_subreddit",
        lambda sub: [a for p in posts_by_sub.get(sub, []) if (a := _to_article(p))],
    )
    monkeypatch.setattr(reddit, "extract_content", lambda articles: articles)


def test_polls_every_configured_subreddit(monkeypatch):
    _stub_reddit(
        monkeypatch,
        {
            "LocalLLaMA": [_post(url="https://example.com/a")],
            "MachineLearning": [_post(url="https://example.com/b")],
        },
    )
    assert {a["url"] for a in reddit.fetch_reddit()} == {
        "https://example.com/a",
        "https://example.com/b",
    }


def test_a_crosspost_to_both_subreddits_is_kept_once(monkeypatch):
    """One release posted to both subs is one story — carrying it twice is two
    scoring calls and a duplicate the dedup step then has to catch."""
    same = _post(url="https://example.com/same")
    _stub_reddit(monkeypatch, {"LocalLLaMA": [same], "MachineLearning": [same]})
    assert len(reddit.fetch_reddit()) == 1


def test_no_posts_yields_nothing(monkeypatch):
    _stub_reddit(monkeypatch, {})
    assert reddit.fetch_reddit() == []
