"""The agent's three verbs against a candidate.

The thing worth pinning hardest is that a candidate leaves the pending state
exactly once and in one direction: approving deletes the row in the same
transaction that inserts the article, rejecting keeps it with the verdict on
it, and a URL that is neither pending nor known comes back as a message the
agent can act on rather than a traceback.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
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
from pipeline.rejects import CANDIDATE_CAP, CONTENT_CAP
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

    def rollback(self) -> None:
        self.rollbacks = getattr(self, "rollbacks", 0) + 1


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
    assert item["publisher_id"] == 7
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


# ─── approval rate ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "approved, rejected, expected",
    [(3, 7, "3/10"), (0, 4, "0/4"), (2, 0, "2/2"), (0, 0, "new")],
)
def test_approval_rate(approved, rejected, expected):
    assert curation.approval_rate(approved, rejected) == expected


# ─── get_content paging ──────────────────────────────────────────────────────


def test_the_first_page_carries_the_text_and_the_links():
    links = {"repo": ["https://github.com/a/b"]}
    row = _pending_row(content="abcdefghij", links=links)
    session = _FakeSession(row)

    page = curation.get_content(session, row.url, limit=4)

    assert page == {
        "text": "abcd",
        "offset": 0,
        "next_offset": 4,
        "total": 10,
        "links": links,
    }


def test_a_later_page_reads_on_without_the_links():
    row = _pending_row(content="abcdefghij", links={"repo": ["x"]})
    session = _FakeSession(row)

    page = curation.get_content(session, row.url, offset=8, limit=4)

    assert page == {"text": "ij", "offset": 8, "next_offset": None, "total": 10}


def test_a_short_article_is_one_page():
    row = _pending_row()
    page = curation.get_content(_FakeSession(row), row.url)
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
def test_page_bounds(total, offset, limit, expected):
    assert curation.page_bounds(total, offset, limit) == expected


def test_get_content_needs_a_pending_candidate():
    row = _pending_row(stage=RejectStage.below_threshold)
    with pytest.raises(curation.CandidateError, match="already"):
        curation.get_content(_FakeSession(row), row.url)


# ─── reject_many ─────────────────────────────────────────────────────────────


def test_reject_many_settles_each_verdict_on_its_own():
    first = _pending_row(url="https://a.example/1")
    third = _pending_row(url="https://a.example/3")
    session = _FakeSession(first, third)

    lines = curation.reject_many(
        session,
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


def test_reject_many_survives_a_failed_write():
    first = _pending_row(url="https://a.example/1")
    second = _pending_row(url="https://a.example/2")
    session = _FakeSession(first, second)
    calls = {"n": 0}

    def commit_fails_once() -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("connection reset")

    session.commit = commit_fails_once  # type: ignore[method-assign]

    lines = curation.reject_many(
        session,
        [
            {"url": first.url, "score": 20, "reason": "r"},
            {"url": second.url, "score": 20, "reason": "r"},
        ],
    )

    assert lines[0] == "Failed https://a.example/1: RuntimeError: connection reset"
    assert lines[1] == "Rejected [20/100] https://a.example/2"
    assert session.rollbacks == 1


# ─── similar and stories: the pure parts ─────────────────────────────────────


def _vecs(*rows: list[float]) -> np.ndarray:
    return np.array(rows, dtype=np.float32)


def test_cosine_distance_is_zero_for_the_same_direction():
    d = curation.cosine_distances(_vecs([1, 0]), _vecs([2, 0], [0, 1], [-1, 0]))
    assert np.allclose(d, [[0, 1, 2]])


def test_cosine_distance_survives_a_zero_vector():
    d = curation.cosine_distances(_vecs([0, 0]), _vecs([1, 0]))
    assert np.isfinite(d).all()


def test_nearest_is_closest_first_within_the_cutoff():
    distances = np.array([0.40, 0.10, 0.50, 0.25])
    assert curation.nearest(distances, cutoff=0.45, limit=8) == [1, 3, 0]
    assert curation.nearest(distances, cutoff=0.45, limit=2) == [1, 3]


def test_coverage_counts_distinct_publishers_under_the_cutoff_and_the_own():
    publishers = ["The Verge", "The Verge", "Wired", "Simon Willison", ""]
    distances = np.array([0.10, 0.20, 0.29, 0.40, 0.05])
    assert curation.covering(publishers, distances, "OpenAI", 0.30) == [
        "OpenAI",
        "The Verge",
        "Wired",
    ]


def test_story_groups_join_pending_rows_with_each_other_and_the_feed():
    # 0, 1 pending and the same story; 2 a feed article on it; 3 a pending
    # candidate on its own; 4 a feed article on nothing queued.
    vecs = _vecs([1, 0, 0], [0.98, 0.1, 0], [0.97, 0.12, 0], [0, 1, 0], [0, 0, 1])
    pending = [True, True, False, True, False]

    groups = curation.story_groups(curation.cosine_distances(vecs, vecs), pending, 0.30)

    assert [sorted(g) for g in groups] == [[0, 1, 2]]


def test_feed_articles_do_not_chain_a_group_through_each_other():
    # Pending 0 is close to article 1; article 2 is close to article 1 but not
    # to 0. Without a pending end on every edge, 2 would ride in through 1.
    distances = np.array(
        [
            [0.0, 0.2, 0.6],
            [0.2, 0.0, 0.2],
            [0.6, 0.2, 0.0],
        ]
    )
    groups = curation.story_groups(distances, [True, False, False], 0.30)
    assert [sorted(g) for g in groups] == [[0, 1]]


def test_a_group_of_feed_articles_alone_is_not_a_story():
    distances = np.array([[0.0, 0.1], [0.1, 0.0]])
    assert curation.story_groups(distances, [False, False], 0.30) == []
