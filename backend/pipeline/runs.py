"""The run record: what one nightly run fetched and queued, and what each polled
publisher last did.

Two places, two jobs. `pipeline_run` keeps one row per run, per-source counts
and the error that stopped a source, which is what the daily mail's liveness
check reads. The Publisher row keeps its own history: when its feed last
answered, when it last gave us something new, and the error it last failed
with. That replaced a per-publisher JSON list stored on every run, which had to
be unpacked across runs to answer "which feeds are broken".

Everything here is best-effort from the run's point of view: `run.py` catches
around it, so a bug in the bookkeeping never changes whether the run succeeded.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from sqlmodel import Session, col, select

from app.catalog.models import Publisher
from app.platform.logging import log
from pipeline.models import PipelineRun


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


def record_run(session: Session, stats: RunStats) -> PipelineRun:
    """Append this run to the pipeline_run table."""
    row = PipelineRun(
        started_at=stats.started_at,
        finished_at=stats.finished_at,
        duration_ms=stats.duration_ms,
        ok=stats.ok,
        sources=[asdict(s) for s in stats.sources],
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log(f"  Recorded pipeline_run #{row.id} (ok={stats.ok})")
    return row


def record_polled(
    session: Session,
    names: Iterable[str],
    errors: dict[str, str],
    now: datetime | None = None,
) -> None:
    """Stamp each publisher a source polled with how the poll went.

    A publisher that answered gets ``last_fetched_at`` and its ``last_error``
    cleared; one that failed keeps its last good fetch and gets the error. A
    publisher that answered with nothing new is an answer, not an error: that
    is ``last_new_at`` falling behind, which only a query asks about.
    """
    wanted = list(dict.fromkeys(names))
    if not wanted:
        return
    now = now or datetime.now(UTC)
    # By name: the feed and lab-watch configs are built from these rows' names.
    publishers = session.exec(
        select(Publisher).where(col(Publisher.name).in_(wanted))
    ).all()
    for p in publishers:
        error = errors.get(p.name)
        if error:
            p.last_error = error
        else:
            p.last_fetched_at = now
            p.last_error = None
        session.add(p)
    session.commit()


def record_new(
    session: Session, publisher_ids: Iterable[int], now: datetime | None = None
) -> None:
    """Stamp ``last_new_at`` on each publisher that got a candidate queued."""
    ids = set(publisher_ids)
    if not ids:
        return
    now = now or datetime.now(UTC)
    for p in session.exec(select(Publisher).where(col(Publisher.id).in_(ids))).all():
        p.last_new_at = now
        session.add(p)
    session.commit()
