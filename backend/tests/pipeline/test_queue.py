"""The end of the nightly funnel: a survivor becomes a pending candidate.

Nothing is scored, summarized or inserted here, so the only things worth
pinning are that every survivor gets a row, that the row is pending rather than
a rejection, and that the step commits — a run that crashes in a later source
must not lose the candidates this one found.
"""

from __future__ import annotations

from pipeline.models import RejectStage
from pipeline.steps.queue import queue_candidates
from pipeline.types import Candidate


class _FakeSession:
    """Just enough Session for the step: it records what it would record."""

    def __init__(self) -> None:
        self.rows: list = []
        self.commits = 0

    def merge(self, obj) -> None:
        self.rows.append(obj)

    def commit(self) -> None:
        self.commits += 1


def _candidate(url: str, **overrides) -> Candidate:
    a: Candidate = {
        "title": "Something about agents",
        "url": url,
        "content": "body",
        "published_date": "2026-09-12T10:00:00+00:00",
        "source": "Hacker News",
        "publisher_id": 7,
        "trust": "medium",
        "publisher_kind": "company",
    }
    return {**a, **overrides}


def test_every_survivor_is_queued_as_pending():
    session = _FakeSession()
    queued = queue_candidates(
        session, [_candidate("https://a.example"), _candidate("https://b.example")]
    )

    assert [row.url for row in session.rows] == [
        "https://a.example",
        "https://b.example",
    ]
    assert {row.stage for row in session.rows} == {RejectStage.pending}
    assert len(queued) == 2


def test_the_row_carries_what_the_agent_will_judge_by():
    session = _FakeSession()
    queue_candidates(
        session,
        [_candidate("https://a.example", traction="120 points, 40 comments")],
    )

    [row] = session.rows
    assert (row.title, row.source, row.publisher_id) == (
        "Something about agents",
        "Hacker News",
        7,
    )
    assert row.traction == "120 points, 40 comments"
    assert row.content == "body"
    assert row.published_at.year == 2026
    # No verdict yet: the agent writes both.
    assert (row.score, row.reason) == (None, None)


def test_the_candidates_are_committed():
    """A later source crashing must not take this source's candidates with it."""
    session = _FakeSession()
    queue_candidates(session, [_candidate("https://a.example")])
    assert session.commits == 1


def test_nothing_to_queue_touches_nothing():
    session = _FakeSession()
    assert queue_candidates(session, []) == []
    assert (session.rows, session.commits) == ([], 0)
