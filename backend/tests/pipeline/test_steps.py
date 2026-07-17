"""The pure cores of the scoring / persist / enrich steps.

These carry the decisions that silently change what gets published — which
article wins a duplicate URL, what counts as passing, whether an LLM rewrite is
allowed to replace a title — so they are pulled out of the I/O steps and pinned
here.
"""

from __future__ import annotations

import pytest

from pipeline.steps.enrich import accept_title
from pipeline.steps.persist import best_per_url
from pipeline.steps.score import apply_scores


def _article(url: str, source: str = "Hacker News", **extra) -> dict:
    return {"title": "A title", "url": url, "source": source, **extra}


# ─── apply_scores ────────────────────────────────────────────────────────────


def test_attaches_each_articles_score_by_url():
    articles = [_article("u1"), _article("u2")]
    scored = apply_scores(articles, {"u1": 80, "u2": 40})
    assert {s["url"]: s["score"] for s in scored} == {"u1": 80, "u2": 40}


def test_article_the_scorer_omitted_scores_zero():
    """A missing score must read as a reject, never as a pass — the scorer
    dropping an item from its response should not let it through unrated."""
    scored = apply_scores([_article("u1")], {})
    assert scored[0]["score"] == 0


def test_sorted_best_first():
    articles = [_article("low"), _article("high"), _article("mid")]
    scored = apply_scores(articles, {"low": 10, "high": 90, "mid": 50})
    assert [s["url"] for s in scored] == ["high", "mid", "low"]


def test_bens_bites_gets_a_source_bonus():
    scored = apply_scores([_article("u1", source="Ben's Bites")], {"u1": 70})
    assert scored[0]["score"] == 80


def test_source_bonus_cannot_push_a_score_past_100():
    scored = apply_scores([_article("u1", source="Ben's Bites")], {"u1": 95})
    assert scored[0]["score"] == 100


def test_other_sources_get_no_bonus():
    scored = apply_scores([_article("u1", source="Hacker News")], {"u1": 70})
    assert scored[0]["score"] == 70


def test_does_not_mutate_the_articles_it_is_given():
    articles = [_article("u1")]
    apply_scores(articles, {"u1": 80})
    assert "score" not in articles[0]


def test_preserves_the_rest_of_the_article():
    scored = apply_scores([_article("u1", publisher_id=7, content="body")], {"u1": 80})
    assert scored[0]["publisher_id"] == 7
    assert scored[0]["content"] == "body"


# ─── best_per_url ────────────────────────────────────────────────────────────


def test_same_url_from_two_sources_keeps_the_higher_score():
    """Two sources can surface one URL in a run (an HN post and a feed item for
    the same post); the URL is the identity, so the better score wins."""
    items = [
        _article("dupe", source="Hacker News", score=40),
        _article("dupe", source="Feeds", score=90),
    ]
    best = best_per_url(items)
    assert len(best) == 1
    assert best[0]["score"] == 90
    assert best[0]["source"] == "Feeds"


def test_higher_score_wins_regardless_of_order():
    items = [_article("dupe", score=90), _article("dupe", score=40)]
    assert best_per_url(items)[0]["score"] == 90


def test_distinct_urls_all_survive():
    items = [_article("u1", score=80), _article("u2", score=70)]
    assert len(best_per_url(items)) == 2


def test_empty_input():
    assert best_per_url([]) == []


# ─── accept_title ────────────────────────────────────────────────────────────

_CURRENT = "The original title"
_SOURCE = "Hacker News"


def test_accepts_a_clean_rewrite():
    assert (
        accept_title("A clear specific technical title", _CURRENT, _SOURCE)
        == "A clear specific technical title"
    )


def test_strips_wrappers_before_accepting():
    assert (
        accept_title('"[HN] A clear specific title"', _CURRENT, _SOURCE)
        == "A clear specific title"
    )


@pytest.mark.parametrize("given", [None, "", "   "])
def test_no_rewrite_offered_keeps_the_original(given):
    assert accept_title(given, _CURRENT, _SOURCE) is None


def test_rewrite_identical_to_the_current_title_is_not_a_change():
    assert accept_title(_CURRENT, _CURRENT, _SOURCE) is None


def test_rejects_a_rewrite_that_leaked_the_source_name():
    assert accept_title("Hacker News covers a new model", _CURRENT, _SOURCE) is None


def test_source_leak_check_is_case_insensitive():
    assert accept_title("hacker news covers a model", _CURRENT, _SOURCE) is None


@pytest.mark.parametrize(
    "given, why",
    [
        ("Two words", "under the 3-word minimum"),
        ("word " * 25, "over the 20-word maximum"),
        ("Read more at https://example.com/x", "contains a URL"),
        ("Title with\na newline", "spans lines"),
        ('{"title": "leaked envelope"}', "leaked the JSON envelope"),
        ("这是一个中文标题", "drifted out of English"),
    ],
)
def test_rejects_malformed_rewrites(given, why):
    assert accept_title(given, _CURRENT, _SOURCE) is None, why
