"""Pipeline health: capture per-run stats and email the night's report —
what landed, a short account of what did not, and the funnel behind both.

The fetch and the verdict are an hour apart (the run queues candidates at
04:00, the curation agent reads them at 05:00), so the report is sent by
`pipeline.report` after the agent, not by the run itself. `report_run` stays
for the crash email.

Runs in-process at the end of `pipeline.run`. Everything is best-effort — a bug
here must never change whether the pipeline itself succeeded.

Deliberately not here: statistical anomaly detection (yield drops, dead feeds
measured against a 30-run average). It fired on every daily report and told a
reader nothing they acted on; the numbers it reasoned over are still recorded
in `pipeline_run`, for an agent to look over on its own schedule.
"""

from __future__ import annotations

import html
import os
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, func, select

from app.catalog.models import Article, Publisher
from app.platform.logging import log
from pipeline.models import PipelineRun, Reject, RejectStage
from pipeline.types import RawItem


@dataclass(frozen=True)
class AlertConfig:
    resend_api_key: str | None
    from_email: str | None
    to_email: str | None
    project_name: str


def alert_config() -> AlertConfig:
    """Read lazily, so importing this module needs no alerting environment."""
    resend_api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("EMAILS_FROM_EMAIL")
    to_email = os.environ.get("PIPELINE_ALERT_EMAIL") or from_email
    project_name = os.environ.get("PROJECT_NAME") or "Agentique"
    return AlertConfig(
        resend_api_key=resend_api_key,
        from_email=from_email,
        to_email=to_email,
        project_name=project_name,
    )


# ─── Tunables ─────────────────────────────────────────────────────────────────

STALE_RUN_HOURS = 26  # older than this with no success → "pipeline may be down"
# How far back the nightly report looks. One window covers the 04:00 run and the
# 05:00 curation session together, which is the night a reader is asking about.
REPORT_WINDOW_HOURS = 24
# Publishers named in the "did not land" line. Enough to show which outlet is
# filling the queue with noise, few enough to stay one sentence.
LOUDEST_PUBLISHERS = 3


# ─── In-memory stats (populated during the run) ───────────────────────────────


@dataclass
class InsertedArticle:
    """One article that landed in the catalog — the report's headline content."""

    id: int
    title: str
    url: str
    score: int
    publisher: str


@dataclass
class SourceStats:
    """Funnel counts for one source in one run. Every drop is accounted for:
    fetched → off-topic → known → dead → dup → queued.

    ``queued`` is what the run ends with — candidates written for the curation
    agent, which inserts them itself once it has read them."""

    # `source` here is the run-level fetcher label (Hacker News / Newsletter /
    # Feeds), not a publisher — see `PublisherStats` below for per-publisher
    # granularity within "Feeds".
    source: str
    fetched: int = 0
    filtered_off_topic: int = 0
    filtered_known: int = 0
    filtered_dead: int = 0
    filtered_thin_repo: int = 0
    deduped: int = 0
    queued: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class PublisherStats:
    """Fetch counts for one publisher within the "Feeds" source in one run —
    the granularity ``SourceStats`` can't give, since "Feeds" aggregates every
    RSS/substack publisher under one label."""

    name: str
    fetched: int = 0
    error: str | None = None


@dataclass
class RunStats:
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    duration_ms: int | None = None
    ok: bool = False
    sources: list[SourceStats] = field(default_factory=list)
    publishers: list[PublisherStats] = field(default_factory=list)

    def source(self, label: str) -> SourceStats:
        s = SourceStats(source=label)
        self.sources.append(s)
        return s

    def record_publishers(
        self,
        expected_names: tuple[str, ...],
        fetched: Sequence[RawItem],
        errors: dict[str, str],
    ) -> None:
        """Record per-publisher fetch counts for one source's run.

        ``expected_names`` is every publisher this source was supposed to
        poll, so a publisher that fetched nothing still gets a row (fetched=0)
        instead of silently disappearing from the stats.
        """
        fetched_counts: dict[str, int] = {}
        for a in fetched:
            fetched_counts[a["source"]] = fetched_counts.get(a["source"], 0) + 1

        for name in expected_names:
            self.publishers.append(
                PublisherStats(
                    name=name,
                    fetched=fetched_counts.get(name, 0),
                    error=errors.get(name),
                )
            )

    def finish(self, ok: bool) -> None:
        self.finished_at = datetime.now(UTC)
        self.duration_ms = int(
            (self.finished_at - self.started_at).total_seconds() * 1000
        )
        self.ok = ok


# ─── Persistence ──────────────────────────────────────────────────────────────


def record_run(session: Session, stats: RunStats) -> PipelineRun:
    """Append this run to the pipeline_run table."""
    row = PipelineRun(
        started_at=stats.started_at,
        finished_at=stats.finished_at,
        duration_ms=stats.duration_ms,
        ok=stats.ok,
        sources=[asdict(s) for s in stats.sources],
        publishers=[asdict(p) for p in stats.publishers],
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    log(f"  Recorded pipeline_run #{row.id} (ok={stats.ok})")
    return row


# ─── Dead-man's-switch (runs at the START of each run) ─────────────────────────


def check_liveness(session: Session) -> None:
    """Alert if there hasn't been a successful run in STALE_RUN_HOURS.

    Catches the case where a previous night's run died so hard it recorded
    nothing. Runs at the start of the next scheduled invocation.
    """
    last = session.exec(
        select(PipelineRun)
        .where(col(PipelineRun.ok).is_(True))
        .order_by(col(PipelineRun.finished_at).desc())
    ).first()
    if last is None or last.finished_at is None:
        return  # first ever successful run — nothing to compare against
    age = datetime.now(UTC) - last.finished_at
    if age > timedelta(hours=STALE_RUN_HOURS):
        hours = age.total_seconds() / 3600
        _send_alert(
            subject="Pipeline may be down",
            body=(
                f"No successful pipeline run in {hours:.0f}h "
                f"(last success: {last.finished_at:%Y-%m-%d %H:%M UTC}).\n"
                "Tonight's run is starting now. If this keeps arriving, the "
                "pipeline container or its schedule is broken."
            ),
        )


# ─── Report (runs at the END of each run) ────────────────────────────────────


def report_run(stats: RunStats) -> None:
    """Email what this run queued, plus the funnel behind it."""
    subject = "Pipeline run report" if stats.ok else "Pipeline run CRASHED"
    _send_alert(subject=subject, body=_format_report(stats))
    log(f"  Reported {sum(s.queued for s in stats.sources)} queued candidate(s)")


def _format_report(stats: RunStats) -> str:
    queued = sum(s.queued for s in stats.sources)
    lines = [f"{queued} candidate(s) queued for review.", ""]
    lines += _funnel_section(stats.sources)

    errors = _errors(stats)
    if errors:
        lines += ["", "ERRORS", "======"]
        lines += [f"  - {e}" for e in errors]

    dur = f"{stats.duration_ms / 1000:.0f}s" if stats.duration_ms else "?"
    lines += ["", f"Run {'OK' if stats.ok else 'CRASHED'} in {dur}."]
    return "\n".join(lines)


def _funnel_section(sources: Sequence[SourceStats]) -> list[str]:
    lines = ["THIS RUN", "========"]
    for s in sources:
        row = (
            f"  {s.source}: fetched {s.fetched} "
            f"→ off-topic -{s.filtered_off_topic} "
            f"→ known -{s.filtered_known} "
            f"→ dead -{s.filtered_dead} "
            f"→ thin-repo -{s.filtered_thin_repo} "
            f"→ dup -{s.deduped} "
            f"→ queued {s.queued}"
        )
        if s.errors:
            row += f"   [errors: {len(s.errors)}]"
        lines.append(row)
    return lines


def _errors(stats: RunStats) -> list[str]:
    """Errors are facts about this run, not a judgement about it — a failed
    source or a feed that 403s belongs in the daily report either way."""
    out = [f"{s.source}: {e}" for s in stats.sources for e in s.errors]
    out += [f"{p.name}: fetch failed — {p.error}" for p in stats.publishers if p.error]
    return out


# ─── Nightly report (runs after the curation agent) ──────────────────────────


@dataclass(frozen=True)
class CurationDay:
    """One night, end to end: what the agent published, and what it did not.

    The rejects are counts and names on purpose. Twenty turned-down articles
    listed one per line is the part of the old report nobody read; what a reader
    acts on is which outlet is filling the queue and whether the pile is
    growing. The verdicts themselves are in the ledger for whoever wants them.
    """

    approved: list[InsertedArticle]
    rejected: int
    loudest: list[tuple[str, int]]
    still_pending: int
    sources: list[SourceStats]
    errors: list[str]


def _source_stats(run: PipelineRun | None) -> list[SourceStats]:
    """Rebuild a recorded run's per-source counts from its stored JSON.

    Keys the dataclass does not have are dropped and missing ones keep their
    default, so a run recorded before a counter existed still reports.
    """
    if run is None:
        return []
    known = {f.name for f in fields(SourceStats)}
    return [
        SourceStats(**{k: v for k, v in source.items() if k in known})
        for source in run.sources
    ]


def curation_summary(session: Session) -> CurationDay:
    """Read the night out of the database: articles in, candidates turned down."""
    cutoff = datetime.now(UTC) - timedelta(hours=REPORT_WINDOW_HOURS)

    approved = session.exec(
        select(Article, Publisher)
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id), isouter=True)
        .where(col(Article.created_at) >= cutoff)
        .order_by(col(Article.score).desc())
    ).all()

    # Counted over what this window queued, not over what the agent touched:
    # a reject keeps the `created_at` of the night its candidate was written,
    # so this is "of last night's candidates, how many were turned down".
    rejected_rows = session.exec(
        select(func.count(), Publisher.name)  # ty: ignore[missing-argument]
        .select_from(Reject)
        .join(Publisher, col(Publisher.id) == col(Reject.publisher_id), isouter=True)
        .where(
            col(Reject.stage) == RejectStage.below_threshold,
            col(Reject.created_at) >= cutoff,
        )
        .group_by(col(Publisher.name))
        .order_by(func.count().desc())
    ).all()

    still_pending = session.exec(
        select(func.count())
        .select_from(Reject)
        .where(  # ty: ignore[missing-argument]
            col(Reject.stage) == RejectStage.pending
        )
    ).one()

    last_run = session.exec(
        select(PipelineRun).order_by(col(PipelineRun.started_at).desc())
    ).first()
    sources = _source_stats(last_run)

    return CurationDay(
        approved=[
            InsertedArticle(
                id=a.id or 0,
                title=a.title,
                url=a.url,
                score=a.score,
                publisher=p.name if p else "",
            )
            for a, p in approved
        ],
        rejected=sum(count for count, _ in rejected_rows),
        loudest=[
            (name or "unknown", count)
            for count, name in rejected_rows[:LOUDEST_PUBLISHERS]
        ],
        still_pending=still_pending,
        sources=sources,
        errors=[f"{s.source}: {e}" for s in sources for e in s.errors],
    )


def report_curation(session: Session) -> None:
    """Email the night's one report. Best-effort, like every other alert."""
    day = curation_summary(session)
    subject = (
        f"{len(day.approved)} article(s) landed" if day.approved else "Nothing landed"
    )
    _send_alert(subject=subject, body=_format_curation(day))
    log(f"  Reported {len(day.approved)} landed, {day.rejected} turned down")


def _format_curation(day: CurationDay) -> str:
    heading = f"LANDED ({len(day.approved)})"
    lines = [heading, "=" * len(heading)]
    if day.approved:
        for a in day.approved:
            byline = f" — {a.publisher}" if a.publisher else ""
            lines.append(f"  [{a.score}/100] {a.title}{byline}")
            lines.append(f"    {a.url}")
    else:
        lines.append("  Nothing was published. If that is not what you expected,")
        lines.append("  the curation session is the first thing to check.")

    lines += ["", "DID NOT LAND", "============"]
    if day.rejected:
        loudest = ", ".join(f"{name} {count}" for name, count in day.loudest)
        lines.append(f"  {day.rejected} turned down. Loudest: {loudest}.")
    else:
        lines.append("  Nothing turned down.")
    lines.append(
        f"  {day.still_pending} candidate(s) still waiting on a verdict."
        if day.still_pending
        else "  Queue empty — every candidate got a verdict."
    )

    lines += [""] + _funnel_section(day.sources)

    if day.errors:
        lines += ["", "ERRORS", "======"] + [f"  - {e}" for e in day.errors]

    return "\n".join(lines)


# ─── Email (Resend) ─────────────────────────────────────────────────────────


def _send_alert(subject: str, body: str) -> None:
    cfg = alert_config()
    if not (cfg.resend_api_key and cfg.from_email and cfg.to_email):
        log(f"  [alert suppressed — email env not set] {subject}\n{body}")
        return

    try:
        import resend

        resend.api_key = cfg.resend_api_key
        resend.Emails.send(
            {
                "from": f"{cfg.project_name} pipeline <{cfg.from_email}>",
                "to": cfg.to_email,
                "subject": f"[{cfg.project_name}] {subject}",
                "html": f"<pre>{html.escape(body)}</pre>",
            }
        )
        log(f"  Alert emailed to {cfg.to_email}: {subject}")
    except Exception as e:
        log(f"  Alert send failed: {e}")
