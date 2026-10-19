"""What a ledger row keeps, and what it must strip to be insertable at all."""

from __future__ import annotations

from collections.abc import Generator
from typing import cast

import pytest
from sqlmodel import Session, col, delete, select

from app.core.db.factories import create_random_publisher, random_lower_string
from app.core.db.ledger import (
    CANDIDATE_CAP,
    CONTENT_CAP,
    LedgerItem,
    Reject,
    RejectStage,
    record_reject,
)
from app.core.db.publisher import Publisher

URL = f"https://example.com/{random_lower_string()}"


class _FakeSession:
    def __init__(self) -> None:
        self.rows: list[Reject] = []

    def merge(self, obj: Reject) -> None:
        self.rows.append(obj)


def _session() -> tuple[Session, list[Reject]]:
    """A session that keeps what `record_reject` merges, and the rows it kept."""
    fake = _FakeSession()
    return cast("Session", fake), fake.rows


def _candidate(**overrides: object) -> LedgerItem:
    a: LedgerItem = {
        "title": "A repo",
        "url": "https://github.com/someone/thing",
        "content": "body",
        "published_date": "2026-09-12T10:00:00+00:00",
        "source": "Hacker News",
        "publisher_id": 7,
        "traction": "3 points, 0 comments on Hacker News",
    }
    return cast("LedgerItem", {**a, **overrides})


def test_keeps_what_the_step_saw() -> None:
    session, rows = _session()
    record_reject(session, _candidate(), RejectStage.thin_repo, detail={"stars": 4})
    [row] = rows
    assert row.stage == RejectStage.thin_repo
    assert (row.title, row.source, row.publisher_id) == ("A repo", "Hacker News", 7)
    assert row.traction == "3 points, 0 comments on Hacker News"
    assert row.published_at is not None
    assert row.published_at.year == 2026
    assert row.detail == {"stars": 4}


def test_caps_content_and_strips_nul_bytes() -> None:
    """Postgres refuses a NUL in a text column, and the failed commit would take
    the whole source down with it."""
    session, rows = _session()
    content = "a\x00b" + "x" * (CONTENT_CAP * 2)
    record_reject(
        session, _candidate(title="t\x00", content=content), RejectStage.prefilter
    )
    [row] = rows
    assert row.title == "t"
    assert row.content is not None
    assert "\x00" not in row.content
    assert len(row.content) < CONTENT_CAP


def test_a_pending_candidate_keeps_the_article_for_the_agent_to_read() -> None:
    session, rows = _session()
    record_reject(
        session, _candidate(content="x" * (CANDIDATE_CAP * 2)), RejectStage.pending
    )
    assert rows[0].content is not None
    assert len(rows[0].content) == CANDIDATE_CAP


def test_empty_content_is_stored_as_null() -> None:
    session, rows = _session()
    record_reject(session, _candidate(content=""), RejectStage.prefilter)
    assert rows[0].content is None


def test_keeps_the_links_extraction_found() -> None:
    session, rows = _session()
    links = {"repo": ["https://github.com/someone/thing"]}
    record_reject(session, _candidate(links=links), RejectStage.pending)
    assert rows[0].links == links


def test_no_links_is_stored_as_null() -> None:
    session, rows = _session()
    record_reject(session, _candidate(links={}), RejectStage.pending)
    assert rows[0].links is None


@pytest.fixture
def publisher(db: Session) -> Generator[Publisher]:
    p = create_random_publisher(db)
    yield p
    db.rollback()
    db.exec(delete(Reject).where(col(Reject.publisher_id) == p.id))
    db.exec(delete(Publisher).where(col(Publisher.id) == p.id))
    db.commit()


def _stored(
    db: Session,
    publisher: Publisher,
    stage: RejectStage = RejectStage.pending,
    **overrides: object,
) -> Reject:
    record_reject(
        db, _candidate(publisher_id=publisher.id, url=URL, **overrides), stage
    )
    db.commit()
    row = db.get(Reject, URL)
    assert row is not None
    db.refresh(row)
    return row


def test_no_detail_is_sql_null_not_json_null(db: Session, publisher: Publisher) -> None:
    """`detail IS NULL` is how the ledger asks for rows without evidence."""
    _stored(db, publisher)
    found = db.exec(select(Reject.url).where(col(Reject.detail).is_(None))).all()
    assert URL in found


def test_recording_a_url_again_overwrites_its_row(
    db: Session, publisher: Publisher
) -> None:
    """The nightly run can meet a URL it already queued; the row is replaced,
    not duplicated, so the commit does not fail on the primary key."""
    _stored(db, publisher, title="first")
    row = _stored(db, publisher, title="second", stage=RejectStage.prefilter)
    assert (row.title, row.stage) == ("second", RejectStage.prefilter)


def test_nul_bytes_and_a_bad_date_still_commit(
    db: Session, publisher: Publisher
) -> None:
    row = _stored(
        db, publisher, title="a\x00b", content="c\x00d", published_date="not a date"
    )
    assert (row.title, row.content, row.published_at) == ("ab", "cd", None)
