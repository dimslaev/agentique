"""What a reject row keeps, and what it must strip to be insertable at all."""

from __future__ import annotations

from pipeline.models import RejectStage
from pipeline.rejects import CANDIDATE_CAP, CONTENT_CAP, record_reject
from pipeline.types import Candidate


class _FakeSession:
    def __init__(self) -> None:
        self.rows: list = []

    def merge(self, obj) -> None:
        self.rows.append(obj)


def _candidate(**overrides) -> Candidate:
    a: Candidate = {
        "title": "A repo",
        "url": "https://github.com/someone/thing",
        "content": "body",
        "published_date": "2026-09-12T10:00:00+00:00",
        "source": "Hacker News",
        "publisher_id": 7,
        "trust": "medium",
        "traction": "3 points, 0 comments on Hacker News",
    }
    return {**a, **overrides}


def test_keeps_what_the_step_saw():
    session = _FakeSession()
    record_reject(session, _candidate(), RejectStage.thin_repo, detail={"stars": 4})
    [row] = session.rows
    assert row.stage == RejectStage.thin_repo
    assert (row.title, row.source, row.publisher_id) == ("A repo", "Hacker News", 7)
    assert row.traction == "3 points, 0 comments on Hacker News"
    assert row.published_at.year == 2026
    assert row.detail == {"stars": 4}


def test_caps_content_and_strips_nul_bytes():
    """Postgres refuses a NUL in a text column, and the failed commit would take
    the whole source down with it."""
    session = _FakeSession()
    content = "a\x00b" + "x" * (CONTENT_CAP * 2)
    record_reject(
        session, _candidate(title="t\x00", content=content), RejectStage.prefilter
    )
    [row] = session.rows
    assert row.title == "t"
    assert "\x00" not in row.content
    assert len(row.content) < CONTENT_CAP


def test_a_pending_candidate_keeps_the_article_for_the_agent_to_read():
    session = _FakeSession()
    record_reject(
        session, _candidate(content="x" * (CANDIDATE_CAP * 2)), RejectStage.pending
    )
    assert len(session.rows[0].content) == CANDIDATE_CAP


def test_empty_content_is_stored_as_null():
    session = _FakeSession()
    record_reject(session, _candidate(content=""), RejectStage.prefilter)
    assert session.rows[0].content is None


def test_keeps_the_links_extraction_found():
    session = _FakeSession()
    links = {"repo": ["https://github.com/someone/thing"]}
    record_reject(session, _candidate(links=links), RejectStage.pending)
    assert session.rows[0].links == links


def test_no_links_is_stored_as_null():
    session = _FakeSession()
    record_reject(session, _candidate(links={}), RejectStage.pending)
    assert session.rows[0].links is None
