"""The agent's three verbs against a candidate.

The thing worth pinning hardest is that a candidate leaves the pending state
exactly once and in one direction: approving deletes the row in the same
transaction that inserts the article, rejecting keeps it with the verdict on
it, and a URL that is neither pending nor known comes back as a message the
agent can act on rather than a traceback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast

import numpy as np
import pytest
from sqlmodel import Session

from app.core.db.article import Article, ArticleKind
from app.core.db.ledger import CANDIDATE_CAP, CONTENT_CAP, Reject, RejectStage
from app.core.db.publisher import Publisher, PublisherKind, PublisherType, TrustLevel
from app.features.curation import coverage
from app.features.curation import service as curation
from app.features.curation.model import (
    CandidateError,
    Persisted,
    ProcessedArticle,
    Summarized,
)
from app.features.curation.tags import Vocabulary


class _FakeSession:
    """Just enough Session for the module: `get` by primary key, and a record
    of what was written."""

    def __init__(self, *rows: Reject | Publisher) -> None:
        self.rejects = {r.url: r for r in rows if isinstance(r, Reject)}
        self.publishers = {p.id: p for p in rows if isinstance(p, Publisher)}
        self.articles: dict[int, Article] = {}
        self.deleted: list[object] = []
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.fail_commits = 0

    def get(self, model: type[object], key: str | int) -> object:
        if model is Reject:
            return self.rejects.get(str(key))
        if model is Article:
            return self.articles.get(int(key))
        return self.publishers.get(int(key))

    def delete(self, obj: object) -> None:
        self.deleted.append(obj)

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        if self.fail_commits:
            self.fail_commits -= 1
            raise RuntimeError("connection reset")
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    @property
    def session(self) -> Session:
        return cast(Session, self)


def _publisher(kind: PublisherKind = PublisherKind.individual) -> Publisher:
    return Publisher(
        id=7,
        name="Simon Willison",
        slug="simon-willison",
        kind=kind,
        type=PublisherType.rss,
        trust=TrustLevel.high,
        topic_gated=False,
    )


def _pending_row(**overrides: object) -> Reject:
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


@dataclass
class _Published:
    """What the insert, the tags and the embedding were handed."""

    inserted: list[Summarized] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    embedded: list[ProcessedArticle] = field(default_factory=list)


@pytest.fixture
def stub_publish(monkeypatch: pytest.MonkeyPatch) -> _Published:
    """Stand in for the insert and the embedding, and record what they were
    handed."""
    seen = _Published()

    def insert(_session: object, items: list[Summarized]) -> list[Persisted]:
        seen.inserted = items
        return [{**items[0], "id": 42}]

    def write_tags(
        _session: object, _article_id: int, slugs: list[str], _vocab: object
    ) -> None:
        seen.tags = slugs

    def embed(_session: object, items: list[ProcessedArticle]) -> None:
        seen.embedded = items

    monkeypatch.setattr(curation, "insert_articles", insert)
    monkeypatch.setattr(curation, "load_vocabulary", lambda session: VOCAB)
    monkeypatch.setattr(curation, "write_article_tags", write_tags)
    monkeypatch.setattr(curation, "embed_articles", embed)
    return seen


def _approve(
    session: _FakeSession,
    url: str,
    score: int = 84,
    reason: str = "r",
    summary: str = "s",
    *,
    kind: str = "post",
    tags: tuple[str, ...] = ("agents",),
    publisher_kind: str | None = None,
    publisher_name: str | None = None,
) -> int:
    return curation.approve(
        session.session,
        url,
        score,
        reason,
        summary,
        kind,
        list(tags),
        publisher_kind,
        publisher_name,
    )


def test_approving_publishes_and_clears_the_candidate(
    stub_publish: _Published,
) -> None:
    row = _pending_row()
    session = _FakeSession(row, _publisher())

    article_id = _approve(
        session, row.url, 84, "Open weights, downloadable today.", "A summary."
    )

    assert article_id == 42
    # Deleted, not left pending: the URL is an Article now, and
    # `filter_known_urls` reads either one.
    assert session.deleted == [row]
    [item] = stub_publish.inserted
    assert (item["score"], item["score_reason"]) == (
        84,
        "Open weights, downloadable today.",
    )
    assert item["summary"] == "A summary."
    assert item["publisher_id"] == 7
    # The stored text is the article: approving never fetches the page again.
    assert item["content"] == "the stored two thousand characters"
    assert stub_publish.embedded[0]["id"] == 42


def test_the_agents_labels_are_written(stub_publish: _Published) -> None:
    row = _pending_row()
    article = Article(id=42, title="t", url=row.url, publisher_id=7, score=84)
    session = _FakeSession(row, _publisher())
    session.articles = {42: article}

    _approve(session, row.url, kind="Post", tags=("agents", "not-a-tag"))

    assert article.kind == ArticleKind.post
    # Off-list tags are dropped, never minted.
    assert stub_publish.tags == ["agents"]


@pytest.mark.usefixtures("stub_publish")
def test_the_aggregator_that_found_it_is_kept() -> None:
    row = _pending_row(source="Hacker News")
    article = Article(id=42, title="t", url=row.url, publisher_id=7, score=84)
    session = _FakeSession(row, _publisher())
    session.articles = {42: article}

    _approve(session, row.url)

    assert article.found_via == "Hacker News"


@pytest.mark.usefixtures("stub_publish")
def test_a_feeds_own_item_was_found_via_nothing() -> None:
    row = _pending_row(source="Simon Willison")
    article = Article(id=42, title="t", url=row.url, publisher_id=7, score=84)
    session = _FakeSession(row, _publisher())
    session.articles = {42: article}

    _approve(session, row.url)

    assert article.found_via is None


@pytest.mark.usefixtures("stub_publish")
def test_approving_names_a_new_publisher() -> None:
    publisher = _publisher(PublisherKind.unknown)
    row = _pending_row()
    session = _FakeSession(row, publisher)

    _approve(session, row.url, publisher_kind="Individual", publisher_name=" Simon ")

    assert publisher.kind == PublisherKind.individual
    assert publisher.name == "Simon"


@pytest.mark.usefixtures("stub_publish")
def test_a_publishers_kind_once_set_stays() -> None:
    """The agent cannot relabel a publisher from one night to the next."""
    publisher = _publisher(PublisherKind.individual)
    row = _pending_row()
    session = _FakeSession(row, publisher)

    _approve(session, row.url, publisher_kind="company", publisher_name="Other")

    assert publisher.kind == PublisherKind.individual
    assert publisher.name == "Simon Willison"


@pytest.mark.usefixtures("stub_publish")
def test_the_url_host_overrules_the_agents_kind() -> None:
    url = "https://github.com/someone/thing"
    row = _pending_row(url=url)
    article = Article(id=42, title="t", url=url, publisher_id=7, score=84)
    session = _FakeSession(row, _publisher())
    session.articles = {42: article}

    _approve(session, url, kind="blog")

    assert article.kind == ArticleKind.repo


@pytest.mark.parametrize(
    "labels, message",
    [
        ({"kind": "podcast"}, "Unknown kind"),
        ({"kind": "blog"}, "Unknown kind"),
        ({}, "new publisher; pass publisher_kind"),
        ({"publisher_kind": "community"}, "Unknown publisher_kind"),
    ],
)
def test_a_bad_label_leaves_the_candidate_pending(
    stub_publish: _Published, labels: dict[str, str], message: str
) -> None:
    row = _pending_row()
    unknown = "publisher_kind" in labels or not labels
    session = _FakeSession(
        row, _publisher(PublisherKind.unknown if unknown else PublisherKind.individual)
    )

    with pytest.raises(CandidateError, match=message):
        _approve(
            session,
            row.url,
            kind=labels.get("kind", "post"),
            publisher_kind=labels.get("publisher_kind"),
        )
    assert session.deleted == []
    assert stub_publish.inserted == []


def test_rejecting_keeps_the_row_with_the_verdict_on_it() -> None:
    row = _pending_row()
    session = _FakeSession(row)

    curation.reject(
        session.session, row.url, 32, "Console steps for one vendor's service."
    )

    assert row.stage == RejectStage.below_threshold
    assert (row.score, row.reason) == (32, "Console steps for one vendor's service.")
    assert session.commits == 1
    # Same stage the scorer wrote, so one query answers "what did we turn down"
    # across both judges.
    assert session.deleted == []


def test_rejecting_trims_the_full_text_back_to_the_ledger_cap() -> None:
    """A candidate carries the whole article so the agent can read it; a settled
    reject keeps only what the ledger keeps for every other reject."""
    row = _pending_row(content="x" * (CONTENT_CAP * 5))
    session = _FakeSession(row)

    curation.reject(session.session, row.url, 20, "reason")

    assert len(row.content or "") == CONTENT_CAP


def test_a_url_that_was_never_queued_is_a_message_not_a_traceback() -> None:
    session = _FakeSession()
    with pytest.raises(CandidateError, match="No candidate for"):
        curation.reject(session.session, "https://unknown.example", 10, "reason")


def test_a_candidate_cannot_be_judged_twice() -> None:
    row = _pending_row(stage=RejectStage.below_threshold)
    session = _FakeSession(row, _publisher())

    with pytest.raises(CandidateError, match="already"):
        _approve(session, row.url, 90)


def test_a_candidate_with_no_publisher_is_not_published(
    stub_publish: _Published,
) -> None:
    """Every Article has a publisher; a candidate that somehow lost one is a bug
    to look at, not a row to force in."""
    row = _pending_row(publisher_id=None)
    session = _FakeSession(row)

    with pytest.raises(CandidateError, match="no publisher"):
        _approve(session, row.url, 90)
    assert stub_publish.inserted == []


# ─── approval rate ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "approved, rejected, expected",
    [(3, 7, "3/10"), (0, 4, "0/4"), (2, 0, "2/2"), (0, 0, "new")],
)
def test_approval_rate(approved: int, rejected: int, expected: str) -> None:
    assert curation.approval_rate(approved, rejected) == expected


# ─── get_content paging ──────────────────────────────────────────────────────


def test_the_first_page_carries_the_text_and_the_links() -> None:
    links = {"repo": ["https://github.com/a/b"]}
    row = _pending_row(content="abcdefghij", links=links)
    session = _FakeSession(row)

    page = curation.get_content(session.session, row.url, limit=4)

    assert page == {
        "text": "abcd",
        "offset": 0,
        "next_offset": 4,
        "total": 10,
        "links": links,
    }


def test_a_later_page_reads_on_without_the_links() -> None:
    row = _pending_row(content="abcdefghij", links={"repo": ["x"]})
    session = _FakeSession(row)

    page = curation.get_content(session.session, row.url, offset=8, limit=4)

    assert page == {"text": "ij", "offset": 8, "next_offset": None, "total": 10}


def test_a_short_article_is_one_page() -> None:
    row = _pending_row()
    page = curation.get_content(_FakeSession(row).session, row.url)
    assert page["text"] == "the stored two thousand characters"
    assert page["next_offset"] is None
    assert page["links"] == {}


@pytest.mark.parametrize(
    "total, offset, limit, expected",
    [
        (10, 0, 4, (0, 4)),
        (10, 8, 4, (8, 10)),
        (10, -5, 4, (0, 4)),  # a negative offset reads from the start
        (10, 20, 4, (10, 10)),  # past the end is an empty page, not an error
        (10, 0, 0, (0, 1)),  # a page is at least one character
        (0, 0, 4, (0, 0)),
        (CANDIDATE_CAP * 2, 0, CANDIDATE_CAP * 2, (0, CANDIDATE_CAP)),
    ],
)
def test_page_bounds(
    total: int, offset: int, limit: int, expected: tuple[int, int]
) -> None:
    assert curation.page_bounds(total, offset, limit) == expected


def test_get_content_needs_a_pending_candidate() -> None:
    row = _pending_row(stage=RejectStage.below_threshold)
    with pytest.raises(CandidateError, match="already"):
        curation.get_content(_FakeSession(row).session, row.url)


# ─── reject_many ─────────────────────────────────────────────────────────────


def test_reject_many_settles_each_verdict_on_its_own() -> None:
    first = _pending_row(url="https://a.example/1")
    third = _pending_row(url="https://a.example/3")
    session = _FakeSession(first, third)

    lines = curation.reject_many(
        session.session,
        [
            {"url": first.url, "score": 20, "reason": "Vendor tutorial."},
            {"url": "https://a.example/2", "score": 30, "reason": "r"},
            {"url": third.url, "score": 25, "reason": "Opinion, no evidence."},
        ],
    )

    assert lines == [
        "Rejected [20/100] https://a.example/1",
        "Skipped https://a.example/2: No candidate for https://a.example/2",
        "Rejected [25/100] https://a.example/3",
    ]
    assert (first.stage, third.stage) == (RejectStage.below_threshold,) * 2
    assert third.reason == "Opinion, no evidence."


def test_reject_many_survives_a_failed_write() -> None:
    first = _pending_row(url="https://a.example/1")
    second = _pending_row(url="https://a.example/2")
    session = _FakeSession(first, second)
    session.fail_commits = 1

    lines = curation.reject_many(
        session.session,
        [
            {"url": first.url, "score": 20, "reason": "r"},
            {"url": second.url, "score": 20, "reason": "r"},
        ],
    )

    assert lines[0] == "Failed https://a.example/1: RuntimeError: connection reset"
    assert lines[1] == "Rejected [20/100] https://a.example/2"
    assert session.rollbacks == 1


# ─── coverage ────────────────────────────────────────────────────────────────


def test_coverage_counts_distinct_publishers_under_the_cutoff_and_the_own() -> None:
    publishers = ["The Verge", "The Verge", "Wired", "Simon Willison", ""]
    distances = np.array([0.10, 0.20, 0.29, 0.40, 0.05], dtype=np.float32)
    assert coverage.covering(publishers, distances, "OpenAI", 0.30) == [
        "OpenAI",
        "The Verge",
        "Wired",
    ]
