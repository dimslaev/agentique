"""The summarize step: nothing is inserted without a summary.

An article whose summary call fails or comes back unusable is dropped before
the insert. A failed call must cost only its own article, and when every call
fails the source has to report it rather than quietly insert nothing.
"""

from __future__ import annotations

import pytest

from pipeline.steps import summarize as summarize_step
from pipeline.steps.summarize import accept_summary, bullet_count
from pipeline.types import Scored

_SUMMARY = "A tiny CLI that tails Postgres logs.\n- Single Go binary\n- Reads libpq"


def _article(url: str) -> Scored:
    return {
        "title": "An LLM thing",
        "url": url,
        "content": "word " * 500,
        "published_date": None,
        "source": "Hacker News",
        "publisher_id": 1,
        "trust": "high",
        "topic_gated": False,
        "score": 80,
    }


class _FakeSession:
    """Just enough Session for the step: it records what it would record."""

    def __init__(self) -> None:
        self.merged: list[str] = []

    def merge(self, obj) -> None:
        self.merged.append(obj.url)

    def commit(self) -> None:
        pass


def _run(monkeypatch, articles, summarizer, session=None):
    class _FakeBaml:
        @staticmethod
        def SummarizeArticle(title, content, bullets):
            return summarizer(title)

    monkeypatch.setattr(summarize_step, "b", _FakeBaml)
    monkeypatch.setattr(summarize_step, "wait_ms", lambda ms: None)
    return summarize_step.summarize_articles(session or _FakeSession(), articles)


# ─── accept_summary ──────────────────────────────────────────────────────────


def test_accepts_a_hook_and_bullets():
    assert accept_summary(_SUMMARY) == _SUMMARY


def test_drops_blank_lines_and_markdown():
    raw = "**A tiny CLI** for logs.\n\n- Single `Go` binary\n"
    assert accept_summary(raw) == "A tiny CLI for logs.\n- Single Go binary"


@pytest.mark.parametrize("given", ["", "  \n\n "])
def test_empty_answer_is_unusable(given):
    assert accept_summary(given) is None


@pytest.mark.parametrize(
    "given, why",
    [
        ('{"summary": "leaked envelope"}', "leaked the JSON envelope"),
        ("这是一个中文摘要", "drifted out of English"),
        (
            "Alibaba's Qwen team (通义千问) ships a preview.\n- 1M context",
            "one native name inside an English summary is enough",
        ),
    ],
)
def test_corrupted_answer_is_unusable(given, why):
    assert accept_summary(given) is None, why


# ─── bullet_count ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "words, bullets", [(0, 3), (399, 3), (400, 4), (1999, 6), (3999, 7), (4000, 8)]
)
def test_bullets_scale_with_length(words, bullets):
    assert bullet_count(words) == bullets


# ─── summarize_articles ──────────────────────────────────────────────────────


def test_attaches_the_summary(monkeypatch):
    kept = _run(monkeypatch, [_article("u1")], lambda title: _SUMMARY)
    assert kept[0]["summary"] == _SUMMARY
    assert kept[0]["score"] == 80


def test_one_failed_call_costs_only_its_own_article(monkeypatch):
    articles = [_article("u1"), _article("u2"), _article("u3")]
    articles[1]["title"] = "fails"

    def summarizer(title):
        if title == "fails":
            raise RuntimeError("provider down")
        return _SUMMARY

    kept = _run(monkeypatch, articles, summarizer)
    assert [a["url"] for a in kept] == ["u1", "u3"]


def test_unusable_summary_is_not_inserted(monkeypatch):
    kept = _run(monkeypatch, [_article("u1")], lambda title: "   ")
    assert kept == []


def test_every_call_failing_raises(monkeypatch):
    """A provider outage has to reach the run report as a source error, not
    read as a night where nothing was worth inserting."""

    def summarizer(_title):
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError, match="provider down"):
        _run(monkeypatch, [_article("u1"), _article("u2")], summarizer)


def test_unusable_summary_is_recorded_so_it_is_not_retried(monkeypatch):
    """Without the record, an article whose summary keeps coming back in
    Chinese would be fetched, scored and summarized again every run."""
    session = _FakeSession()
    _run(monkeypatch, [_article("u1")], lambda title: "这是一个中文摘要", session)
    assert session.merged == ["u1"]


def test_failed_call_is_not_recorded(monkeypatch):
    """A provider outage must not become a permanent reject: the article comes
    back next run."""
    articles = [_article("u1"), _article("u2")]
    articles[1]["title"] = "fails"

    def summarizer(title):
        if title == "fails":
            raise RuntimeError("provider down")
        return _SUMMARY

    session = _FakeSession()
    _run(monkeypatch, articles, summarizer, session)
    assert session.merged == []


def test_empty_input():
    assert summarize_step.summarize_articles(_FakeSession(), []) == []
