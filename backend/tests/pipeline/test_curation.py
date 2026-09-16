"""The agent's three verbs against a candidate.

The thing worth pinning hardest is that a candidate leaves the pending state
exactly once and in one direction: approving deletes the row in the same
transaction that inserts the article, rejecting keeps it with the verdict on
it, and a URL that is neither pending nor known comes back as a message the
agent can act on rather than a traceback.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.catalog.models import Publisher, PublisherKind, PublisherType, TrustLevel
from pipeline import curation
from pipeline.models import Reject, RejectStage


class _FakeSession:
    """Just enough Session for the module: `get` by primary key, and a record
    of what was written."""

    def __init__(self, *rows) -> None:
        self.rejects = {r.url: r for r in rows if isinstance(r, Reject)}
        self.publishers = {p.id: p for p in rows if isinstance(p, Publisher)}
        self.deleted: list = []
        self.added: list = []
        self.commits = 0

    def get(self, model, key):
        if model is Reject:
            return self.rejects.get(key)
        return self.publishers.get(key)

    def delete(self, obj) -> None:
        self.deleted.append(obj)

    def add(self, obj) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.commits += 1


def _publisher() -> Publisher:
    return Publisher(
        id=7,
        name="Simon Willison",
        slug="simon-willison",
        kind=PublisherKind.individual,
        type=PublisherType.rss,
        trust=TrustLevel.high,
        topic_gated=False,
    )


def _pending_row(**overrides) -> Reject:
    row = Reject(
        url="https://simonwillison.net/post",
        stage=RejectStage.pending,
        title="Gemini 3.8 Live",
        source="Feeds",
        publisher_id=7,
        published_at=datetime(2026, 9, 15, tzinfo=UTC),
        content="the stored two thousand characters",
        traction=None,
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


@pytest.fixture
def stub_publish(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stand in for the insert-and-enrich tail, and record what it was handed."""
    seen: dict = {}

    def insert(_session, items):
        seen["inserted"] = items
        return [{**items[0], "id": 42}]

    monkeypatch.setattr(curation, "insert_articles", insert)
    monkeypatch.setattr(curation, "load_vocabulary", lambda session: "vocab")
    monkeypatch.setattr(
        curation,
        "categorize_and_tag_articles",
        lambda _s, items, vocab: seen.setdefault("tagged", (items, vocab)) and [],
    )
    monkeypatch.setattr(
        curation, "embed_articles", lambda _s, items: seen.setdefault("embedded", items)
    )
    # No network in a unit test: the stored text is what gets published.
    monkeypatch.setattr(
        curation, "fetch_and_extract", lambda url, cap: (_ for _ in ()).throw(OSError())
    )
    return seen


def test_approving_publishes_and_clears_the_candidate(stub_publish: dict):
    row = _pending_row()
    session = _FakeSession(row, _publisher())

    article_id = curation.approve(
        session, row.url, 84, "Open weights, downloadable today.", "A summary."
    )

    assert article_id == 42
    # Deleted, not left pending: the URL is an Article now, and
    # `filter_known_urls` reads either one.
    assert session.deleted == [row]
    [item] = stub_publish["inserted"]
    assert (item["score"], item["score_reason"]) == (
        84,
        "Open weights, downloadable today.",
    )
    assert item["summary"] == "A summary."
    assert (item["trust"], item["publisher_kind"]) == ("high", "individual")


def test_approving_falls_back_to_the_stored_text_when_the_page_is_gone(
    stub_publish: dict,
):
    """A newsletter item has no page to re-read. The stored copy is all there
    is, and a failed fetch must never publish an article with less text than
    the pipeline already had."""
    row = _pending_row()
    session = _FakeSession(row, _publisher())

    curation.approve(session, row.url, 70, "reason", "summary")

    [item] = stub_publish["inserted"]
    assert item["content"] == "the stored two thousand characters"


def test_a_longer_re_fetch_wins(monkeypatch: pytest.MonkeyPatch, stub_publish: dict):
    monkeypatch.setattr(curation, "fetch_and_extract", lambda url, cap: "x" * 5000)
    row = _pending_row()
    session = _FakeSession(row, _publisher())

    curation.approve(session, row.url, 70, "reason", "summary")

    assert len(stub_publish["inserted"][0]["content"]) == 5000


def test_a_shorter_re_fetch_does_not_shrink_the_article(
    monkeypatch: pytest.MonkeyPatch, stub_publish: dict
):
    monkeypatch.setattr(curation, "fetch_and_extract", lambda url, cap: "nope")
    row = _pending_row()
    session = _FakeSession(row, _publisher())

    curation.approve(session, row.url, 70, "reason", "summary")

    assert (
        stub_publish["inserted"][0]["content"] == "the stored two thousand characters"
    )


def test_rejecting_keeps_the_row_with_the_verdict_on_it():
    row = _pending_row()
    session = _FakeSession(row)

    curation.reject(session, row.url, 32, "Console steps for one vendor's service.")

    assert row.stage == RejectStage.below_threshold
    assert (row.score, row.reason) == (32, "Console steps for one vendor's service.")
    assert session.commits == 1
    # Same stage the scorer wrote, so one query answers "what did we turn down"
    # across both judges.
    assert session.deleted == []


def test_a_url_that_was_never_queued_is_a_message_not_a_traceback():
    session = _FakeSession()
    with pytest.raises(curation.CandidateError, match="No candidate for"):
        curation.reject(session, "https://unknown.example", 10, "reason")


def test_a_candidate_cannot_be_judged_twice():
    row = _pending_row(stage=RejectStage.below_threshold)
    session = _FakeSession(row, _publisher())

    with pytest.raises(curation.CandidateError, match="already"):
        curation.approve(session, row.url, 90, "reason", "summary")


def test_a_candidate_with_no_publisher_is_not_published(stub_publish: dict):
    """Every Article has a publisher; a candidate that somehow lost one is a bug
    to look at, not a row to force in."""
    row = _pending_row(publisher_id=None)
    session = _FakeSession(row)

    with pytest.raises(curation.CandidateError, match="no publisher"):
        curation.approve(session, row.url, 90, "reason", "summary")
    assert "inserted" not in stub_publish


def test_get_content_returns_the_stored_text():
    row = _pending_row()
    session = _FakeSession(row)
    assert (
        curation.get_content(session, row.url) == "the stored two thousand characters"
    )
