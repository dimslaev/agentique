"""The HN source's two pure gates: the AI keyword pattern every title is
matched against, and the item -> article conversion that applies it alongside
the story/recency checks.
"""

from __future__ import annotations

import time

import pytest

from pipeline.heuristics import AI_TITLE_KEYWORDS
from pipeline.sources import hn
from pipeline.sources.hn import _to_article

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
    assert AI_TITLE_KEYWORDS.search(title)


@pytest.mark.parametrize("title", NON_MATCHES)
def test_skips_non_ai_titles(title: str) -> None:
    assert not AI_TITLE_KEYWORDS.search(title)


# ─── _to_article ─────────────────────────────────────────────────────────────


def _item(**overrides) -> dict:
    """A firebase item as HN serves it, defaulted to one that passes."""
    return {
        "id": 42,
        "type": "story",
        "title": "Qwen3-Max is out",
        "url": "https://example.com/qwen3",
        "time": int(time.time()),
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
