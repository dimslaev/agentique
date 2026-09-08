"""The HN source's pure gates: the AI keyword pattern every title is matched
against, the traction check that asks whether HN's own readers gave the story
anything, and the item -> article conversion that applies both alongside the
story/recency checks.
"""

from __future__ import annotations

import time

import pytest

from pipeline.sources import hn
from pipeline.sources.hn import _to_article, has_traction
from pipeline.topic_gate import is_on_topic

HOUR = 3600

MATCHES = [
    # version suffixes glued to the name — the case bare \b boundaries miss
    "Qwen3-Max is out",
    "Llama4 Scout weights",
    "GPT5 system card",
    "Gemma3 on device",
    "Qwen2.5-VL",
    # Chinese labs
    "Kimi K2 thinking",
    "GLM-4.6 released",
    "MiniMax M2",
    "Hunyuan video model",
    "Ernie 5.0",
    "Huawei Pangu weights",
    # accelerators
    "Nvidia GB200 NVL72 teardown",
    "MI355X vs H200 throughput",
    "Cerebras hits 3000 tok/s",
    "Ironwood TPU",
    "Tenstorrent Blackhole",
    # training / serving
    "vLLM adds speculative decoding",
    "GRPO from scratch",
    "Ollama now supports MLX",
    # agents / tools / evals / safety
    "MCP servers explained",
    "SWE-bench verified results",
    "Prompt injection in Copilot",
    "Mechanistic interpretability of induction heads",
]

# Non-AI titles that a sloppy pattern would catch — mostly prefix collisions
# with the short umbrella terms ("ai", "rag").
NON_MATCHES = [
    "Postgres 18 released",
    "A new CSS layout engine",
    "Rust 1.90 is out",
    "SQLite internals",
    "Aircraft carrier design",
    "Ragged arrays in C",
    "Aiming for simplicity",
    "Airbnb redesign",
    "The economics of shipping containers",
]


@pytest.mark.parametrize("title", MATCHES)
def test_matches_ai_titles(title: str) -> None:
    assert is_on_topic(title)


@pytest.mark.parametrize("title", NON_MATCHES)
def test_skips_non_ai_titles(title: str) -> None:
    assert not is_on_topic(title)


# ─── _to_article ─────────────────────────────────────────────────────────────


def _item(**overrides) -> dict:
    """A firebase item as HN serves it, defaulted to one that passes.

    Aged past the grace window and carrying real points, because that is the
    shape of a story worth keeping — the traction gate is exercised by the
    tests that deliberately vary those two fields.
    """
    return {
        "id": 42,
        "type": "story",
        "title": "Qwen3-Max is out",
        "url": "https://example.com/qwen3",
        "time": int(time.time()) - HOUR * 12,
        "score": 120,
        "descendants": 40,
        **overrides,
    }


def test_converts_a_passing_story():
    article = _to_article(_item())
    assert article is not None
    assert article["url"] == "https://example.com/qwen3"
    assert article["source"] == "Hacker News"
    assert article["content"] == ""


def test_strips_the_show_hn_prefix():
    article = _to_article(_item(title="Show HN: My LLM inference server"))
    assert article is not None
    assert article["title"] == "My LLM inference server"


def test_text_post_falls_back_to_its_hn_permalink():
    """An Ask HN post carries no url; the discussion itself is the article."""
    article = _to_article(_item(url=None, title="Ask HN: best local LLM setup?"))
    assert article is not None
    assert article["url"] == "https://news.ycombinator.com/item?id=42"


@pytest.mark.parametrize(
    "override, why",
    [
        ({}, "not an item at all"),
        ({"type": "comment"}, "a comment, not a story"),
        ({"type": "job"}, "a job ad, not a story"),
        ({"title": ""}, "no title"),
        ({"title": "Postgres 18 released"}, "title is not AI-related"),
        ({"time": int(time.time()) - 60 * 60 * 24 * 30}, "outside the window"),
    ],
)
def test_rejects(override, why):
    item = {} if not override else _item(**override)
    assert _to_article(item) is None, why


def test_an_item_with_no_time_is_kept_and_dated_now():
    """is_within_window treats a missing date as recent on purpose — an HN item
    without a timestamp is a firebase oddity, not a reason to lose the story."""
    article = _to_article(_item(time=None))
    assert article is not None
    assert article["published_date"]


# ─── fetch_hn: top + new ─────────────────────────────────────────────────────


def _stub_hn(monkeypatch, ids_by_feed: dict[str, list[int]]) -> list[int]:
    """Run fetch_hn against canned id lists, recording which ids it looked up.

    Everything that touches the network is replaced: the two listing calls, the
    per-item lookup, and the content extraction pass.
    """
    looked_up: list[int] = []

    def story_ids(label: str, _url: str) -> list[int]:
        return ids_by_feed.get(label, [])

    def fetch_item(item_id: int) -> dict:
        looked_up.append(item_id)
        return _item(id=item_id, url=f"https://example.com/{item_id}")

    monkeypatch.setattr(hn, "_story_ids", story_ids)
    monkeypatch.setattr(hn, "_fetch_item", fetch_item)
    monkeypatch.setattr(hn, "extract_content", lambda articles: articles)
    return looked_up


def test_polls_both_the_top_and_new_listings(monkeypatch):
    """newstories is where a release lands before it trends — dropping it back
    to topstories-only silently halves the source."""
    looked_up = _stub_hn(monkeypatch, {"top": [1, 2], "new": [3, 4]})
    articles = hn.fetch_hn()
    assert sorted(looked_up) == [1, 2, 3, 4]
    assert len(articles) == 4


def test_an_id_on_both_listings_is_fetched_once(monkeypatch):
    """The lists overlap heavily — a new story that trends is on both."""
    looked_up = _stub_hn(monkeypatch, {"top": [1, 2], "new": [2, 3]})
    articles = hn.fetch_hn()
    assert sorted(looked_up) == [1, 2, 3]
    assert len({a["url"] for a in articles}) == 3


def test_both_listings_failing_yields_nothing(monkeypatch):
    _stub_hn(monkeypatch, {})
    assert hn.fetch_hn() == []


# ─── traction gate ───────────────────────────────────────────────────────────
#
# The firehose is every submission, so points and comments are the only thing
# separating a lab release from a two-star repo its author just posted. These
# cover the three cases in ``has_traction``.


def test_an_aged_story_nobody_read_is_held_back():
    assert not has_traction(
        _item(time=int(time.time()) - HOUR * 20, score=3, descendants=0)
    )


def test_points_alone_clear_the_gate():
    assert has_traction(
        _item(time=int(time.time()) - HOUR * 20, score=40, descendants=0)
    )


def test_discussion_alone_clears_the_gate():
    """A story that got argued about is real even when the votes stayed flat."""
    assert has_traction(
        _item(time=int(time.time()) - HOUR * 20, score=2, descendants=25)
    )


def test_a_young_story_is_held_back_not_judged():
    """Every story starts at 1 point, so nothing can be concluded yet. It is
    held, not rejected — the source records nothing, so the next run sees the
    same id again with settled numbers, still inside the 48h window."""
    assert not has_traction(_item(time=int(time.time()) - HOUR, score=1, descendants=0))


def test_a_young_first_party_release_goes_straight_through():
    """The reason newstories is polled at all: a lab's own post is news at zero
    points, and holding it for a day would publish it late."""
    assert has_traction(
        _item(
            time=int(time.time()) - 60,
            score=1,
            descendants=0,
            url="https://openai.com/index/gpt-5-6/",
        )
    )


def test_first_party_matching_covers_subdomains():
    assert has_traction(
        _item(
            time=int(time.time()) - 60,
            score=1,
            url="https://platform.claude.com/docs/en/about-claude/models",
        )
    )


def test_the_gate_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(hn, "hn_min_points", lambda: 0)
    assert has_traction(
        _item(time=int(time.time()) - HOUR * 20, score=0, descendants=0)
    )


def test_a_story_without_traction_never_becomes_an_article():
    assert (
        _to_article(_item(time=int(time.time()) - HOUR * 20, score=1, descendants=0))
        is None
    )


def test_the_article_carries_its_traction_to_the_scorer():
    """Passed on as evidence, not only used as a gate: the scorer put unread
    Show HN repos in the 90s while a title was all it could see.

    Reported even for an article that skipped the gate — a first-party post
    goes through on zero votes, and the scorer should still be told that is
    what happened.
    """
    article = _to_article(
        _item(url="https://openai.com/index/gpt-5-6/", score=7, descendants=1)
    )
    assert article is not None
    assert article["traction"] == "7 points, 1 comments on Hacker News"
