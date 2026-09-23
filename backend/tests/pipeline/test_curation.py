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

from app.catalog.models import (
    Article,
    ArticleKind,
    Category,
    Publisher,
    PublisherKind,
    PublisherType,
    TrustLevel,
)
from pipeline import curation
from pipeline.models import Reject, RejectStage
from pipeline.rejects import CONTENT_CAP
from pipeline.tags import Vocabulary


class _FakeSession:
    """Just enough Session for the module: `get` by primary key, and a record
    of what was written."""

    def __init__(self, *rows) -> None:
        self.rejects = {r.url: r for r in rows if isinstance(r, Reject)}
        self.publishers = {p.id: p for p in rows if isinstance(p, Publisher)}
        self.articles: dict = {}
        self.deleted: list = []
        self.added: list = []
        self.commits = 0

    def get(self, model, key):
        if model is Reject:
            return self.rejects.get(key)
        if model is Article:
            return self.articles.get(key)
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


VOCAB = Vocabulary(
    slug_to_id={"agents": 1, "local-inference": 2},
    slug_to_description={"agents": "Agent frameworks", "local-inference": ""},
)


@pytest.fixture
def stub_publish(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stand in for the insert and the embedding, and record what they were
    handed."""
    seen: dict = {}

    def insert(_session, items):
        seen["inserted"] = items
        return [{**items[0], "id": 42}]

    monkeypatch.setattr(curation, "insert_articles", insert)
    monkeypatch.setattr(curation, "load_vocabulary", lambda session: VOCAB)
    monkeypatch.setattr(
        curation,
        "write_article_tags",
        lambda _s, article_id, slugs, vocab: seen.setdefault("tags", slugs),
    )
    monkeypatch.setattr(
        curation, "embed_articles", lambda _s, items: seen.setdefault("embedded", items)
    )
    return seen


def _approve(session, url, score=84, reason="r", summary="s", **labels):
    labels = {
        "categories": ["models"],
        "kind": "announcement",
        "tags": ["agents"],
    } | labels
    return curation.approve(session, url, score, reason, summary, **labels)


def test_approving_publishes_and_clears_the_candidate(stub_publish: dict):
    row = _pending_row()
    session = _FakeSession(row, _publisher())

    article_id = _approve(
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
    # The stored text is the article: approving never fetches the page again.
    assert item["content"] == "the stored two thousand characters"
    assert stub_publish["embedded"][0]["id"] == 42


def test_the_agents_labels_are_written(stub_publish: dict):
    row = _pending_row()
    article = Article(id=42, title="t", url=row.url, publisher_id=7)
    session = _FakeSession(row, _publisher())
    session.articles = {42: article}

    _approve(
        session,
        row.url,
        categories=["Models", "research", "nope"],
        kind="announcement",
        tags=["agents", "not-a-tag"],
    )

    assert article.categories == [Category.models, Category.research]
    assert article.kind == ArticleKind.announcement
    # Off-list tags are dropped, never minted.
    assert stub_publish["tags"] == ["agents"]


@pytest.mark.usefixtures("stub_publish")
def test_the_url_host_overrules_the_agents_kind():
    url = "https://github.com/someone/thing"
    row = _pending_row(url=url)
    article = Article(id=42, title="t", url=url, publisher_id=7)
    session = _FakeSession(row, _publisher())
    session.articles = {42: article}

    _approve(session, url, kind="blog")

    assert article.kind == ArticleKind.repo


@pytest.mark.parametrize(
    "labels, message",
    [
        ({"categories": ["crypto"]}, "No valid category"),
        ({"categories": []}, "No valid category"),
        ({"kind": "podcast"}, "Unknown kind"),
    ],
)
def test_a_bad_label_leaves_the_candidate_pending(
    stub_publish: dict, labels: dict, message: str
):
    row = _pending_row()
    session = _FakeSession(row, _publisher())

    with pytest.raises(curation.CandidateError, match=message):
        _approve(session, row.url, **labels)
    assert session.deleted == []
    assert "inserted" not in stub_publish


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


def test_rejecting_trims_the_full_text_back_to_the_ledger_cap():
    """A candidate carries the whole article so the agent can read it; a settled
    reject keeps only what the ledger keeps for every other reject."""
    row = _pending_row(content="x" * (CONTENT_CAP * 5))
    session = _FakeSession(row)

    curation.reject(session, row.url, 20, "reason")

    assert len(row.content) == CONTENT_CAP


def test_a_url_that_was_never_queued_is_a_message_not_a_traceback():
    session = _FakeSession()
    with pytest.raises(curation.CandidateError, match="No candidate for"):
        curation.reject(session, "https://unknown.example", 10, "reason")


def test_a_candidate_cannot_be_judged_twice():
    row = _pending_row(stage=RejectStage.below_threshold)
    session = _FakeSession(row, _publisher())

    with pytest.raises(curation.CandidateError, match="already"):
        _approve(session, row.url, 90)


def test_a_candidate_with_no_publisher_is_not_published(stub_publish: dict):
    """Every Article has a publisher; a candidate that somehow lost one is a bug
    to look at, not a row to force in."""
    row = _pending_row(publisher_id=None)
    session = _FakeSession(row)

    with pytest.raises(curation.CandidateError, match="no publisher"):
        _approve(session, row.url, 90)
    assert "inserted" not in stub_publish


def test_get_content_returns_the_stored_text():
    row = _pending_row()
    session = _FakeSession(row)
    assert (
        curation.get_content(session, row.url) == "the stored two thousand characters"
    )
