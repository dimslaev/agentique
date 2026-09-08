"""What a failed scoring batch costs.

On 2026-09-03 one ScoreArticles call failed - all three fallback clients down
at once - and took the whole Feeds source with it: 121 fetched articles, 0
inserted. These pin the two halves of the fix. A failed batch must cost only
its own articles, and those articles must come back on the next run rather
than be recorded as rejected, since apply_scores reads a missing score as 0.
"""

from __future__ import annotations

import pytest

from pipeline.steps import score as score_step
from pipeline.steps.score import SCORE_THRESHOLD
from pipeline.types import Candidate


class _FakeSession:
    """Just enough Session for the scorer: it records what it would record."""

    def __init__(self) -> None:
        self.merged: list[str] = []
        self.commits = 0

    def merge(self, obj) -> None:
        self.merged.append(obj.url)

    def commit(self) -> None:
        self.commits += 1


class _Scored:
    def __init__(self, url: str, score: int) -> None:
        self.url = url
        self.score = score


def _article(url: str) -> Candidate:
    return {
        "title": "An LLM thing",
        "url": url,
        "content": "body",
        "published_date": None,
        "source": "Hacker News",
        "publisher_id": 1,
        "trust": "high",
        "topic_gated": False,
    }


def _run(monkeypatch, articles, scorer):
    """Run score_articles with a stubbed ScoreArticles, returning (kept, session)."""

    class _FakeBaml:
        @staticmethod
        def ScoreArticles(inputs):
            return scorer([i.url for i in inputs])

    monkeypatch.setattr(score_step, "b", _FakeBaml)
    monkeypatch.setattr(score_step, "wait_ms", lambda ms: None)
    monkeypatch.setattr(score_step, "prefilter_keep_drop", lambda s, a: a)
    session = _FakeSession()
    return score_step.score_articles(session, articles), session


def _pass_all(urls):
    return [_Scored(u, 90) for u in urls]


def test_one_failed_batch_does_not_cost_the_other_batches(monkeypatch):
    articles = [_article(f"u{n}") for n in range(score_step.SCORE_BATCH * 3)]

    calls = {"n": 0}

    def scorer(urls):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("provider down")
        return _pass_all(urls)

    kept, _ = _run(monkeypatch, articles, scorer)

    assert calls["n"] == 3
    assert len(kept) == score_step.SCORE_BATCH * 2


def test_a_failed_batchs_articles_are_not_recorded_as_rejected(monkeypatch):
    """The whole point: an unscored article must be free to come back. Writing
    it to ScoredUrl would make filter_known_urls drop it forever."""
    articles = [_article(f"u{n}") for n in range(score_step.SCORE_BATCH * 2)]
    held = {a["url"] for a in articles[: score_step.SCORE_BATCH]}

    calls = {"n": 0}

    def scorer(urls):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("provider down")
        return _pass_all(urls)

    kept, session = _run(monkeypatch, articles, scorer)

    assert {k["url"] for k in kept}.isdisjoint(held)
    assert set(session.merged).isdisjoint(held)


def test_a_sub_threshold_article_is_still_recorded(monkeypatch):
    """The held-article rule must not stop the normal case from recording."""
    articles = [_article("keep"), _article("drop")]
    scores = {"keep": 90, "drop": SCORE_THRESHOLD - 1}

    kept, session = _run(
        monkeypatch, articles, lambda urls: [_Scored(u, scores[u]) for u in urls]
    )

    assert [k["url"] for k in kept] == ["keep"]
    assert session.merged == ["drop"]


def test_every_batch_failing_raises_so_the_source_records_the_error(monkeypatch):
    """A total scorer outage is not a bad call, and the run must not report it
    as a source that simply found nothing."""
    articles = [_article(f"u{n}") for n in range(score_step.SCORE_BATCH * 2)]

    def scorer(_urls):
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError, match="provider down"):
        _run(monkeypatch, articles, scorer)


def test_no_articles_needs_no_call(monkeypatch):
    def scorer(_urls):
        raise AssertionError("should not be called")

    kept, session = _run(monkeypatch, [], scorer)
    assert kept == []
    assert session.commits == 0
