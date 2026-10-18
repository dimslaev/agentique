"""The item as it changes shape on its way down the collect funnel, and the
run's per-source counts.

    RawItem    what a source emits -- title, url, content, date, source
    Candidate  + the publisher it belongs to   (fetch.resolve_publishers)

``Candidate`` subclasses ``RawItem``, so a step that only needs a ``RawItem``
also accepts a ``Candidate``, while a step that needs the publisher cannot be
handed an item that has not been resolved. The funnel ends at the queue: a
candidate becomes a `pending` ledger row, and curation reads it from there with
types of its own.

This replaced a single ``FetchedArticle`` where every key was optional at every
stage. That shape could not say which step filled what, so each step's contract
lived in a docstring and a misordered call failed at runtime with a KeyError
instead of at the call site.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import NotRequired, TypedDict


class RawItem(TypedDict):
    """One item as a source adapter emits it, before anything is known about it.

    ``content`` may be empty at this point: the thin sources (Hacker News,
    Lab Watch, Newsletter) arrive with a blurb or nothing at all, and
    ``fetch._with_content`` fills it before the item goes any further.
    """

    title: str
    url: str
    content: str
    published_date: str | None
    source: str
    # Only the aggregator sources that carry a public reception signal (Hacker
    # News points/comments) have one. Shown to the agent as evidence, not
    # merely used as a gate -- see hn.py.
    traction: NotRequired[str]
    # The repo / model / paper / docs links the article body makes, grouped by
    # ``app.core.extract``. Absent when the text came from nowhere with HTML.
    links: NotRequired[dict[str, list[str]]]


class Candidate(RawItem):
    """An item resolved to the Publisher it came from."""

    publisher_id: int


@dataclass
class SourceStats:
    """One source in one run: how many items it fetched, how many became
    candidates, and the error that stopped it, if one did.

    ``source`` is the run-level fetcher label (Feeds, Hacker News, Newsletter,
    Lab Watch), not a publisher.
    """

    source: str
    fetched: int = 0
    queued: int = 0
    error: str | None = None


@dataclass
class RunStats:
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    duration_ms: int | None = None
    ok: bool = False
    sources: list[SourceStats] = field(default_factory=list)

    def source(self, label: str) -> SourceStats:
        s = SourceStats(source=label)
        self.sources.append(s)
        return s

    def finish(self, ok: bool) -> None:
        self.finished_at = datetime.now(UTC)
        self.duration_ms = int(
            (self.finished_at - self.started_at).total_seconds() * 1000
        )
        self.ok = ok
