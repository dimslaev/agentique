"""Curation's shapes: what the agent reads about a candidate, the verdicts it
hands back, and the article as approving builds it.

The stage types pick up where collect's ``Candidate`` ends, at the ledger row:
approving reads the row and builds a ``Summarized`` from it, which
``publish.insert_articles`` turns into a ``Persisted``. They repeat the fields
rather than subclass collect's types, so the two features share nothing but
the table between them.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class CandidateError(Exception):
    """No pending candidate at that URL — approved already, rejected already,
    or never queued. The agent gets the message, not a traceback."""


class LinkError(Exception):
    """A URL ``check_link`` does not read. The message names the tool that does."""


class CandidatePage(TypedDict):
    """One page of the pending queue. ``next_offset`` is None on the last page."""

    rows: list[dict[str, str]]
    offset: int
    next_offset: int | None
    total: int


class ContentPage(TypedDict):
    """One slice of a candidate's stored text. ``next_offset`` is None on the
    last page; ``links`` rides on the first page only."""

    text: str
    offset: int
    next_offset: int | None
    total: int
    links: NotRequired[dict[str, list[str]]]


class Neighbour(TypedDict):
    """A row beside a candidate: an Article (stage ``published``) or a ledger row."""

    url: str
    title: str
    publisher: str
    stage: str
    score: int | None
    distance: NotRequired[float]


class Similar(TypedDict):
    url: str
    # Distinct publishers carrying this story, the candidate's own included.
    coverage: int
    publishers: list[str]
    rows: list[Neighbour]


class Coverage(TypedDict):
    coverage: int
    publishers: list[str]
    members: list[Neighbour]


class Verdict(TypedDict):
    """One rejection in a `reject_many` batch."""

    url: str
    score: int
    reason: str


class Scored(TypedDict):
    """A candidate the curation agent approved, with the score it gave."""

    title: str
    url: str
    content: str
    published_date: str | None
    source: str
    publisher_id: int
    score: int
    # The agent's one-sentence account of the score.
    score_reason: str | None


class Summarized(Scored):
    """A scored article with the summary the agent wrote. Nothing is inserted
    without one."""

    summary: str


class Persisted(Summarized):
    """A scored article that is now a row: ``id`` is the Article's primary key.

    ``title`` and ``content`` are the sanitized values actually stored, not the
    raw ones the source emitted.
    """

    id: int


class ProcessedArticle(TypedDict):
    """What the embedder needs: a stored article reduced to the fields the
    embedding text is built from."""

    id: int
    url: str
    title: str
    score: int
    snippet: str
