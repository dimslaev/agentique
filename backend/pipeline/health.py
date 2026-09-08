"""Pipeline health: capture per-run stats, detect anomalies, email a report
every run (anomaly alert or clean daily summary).

Runs in-process at the end of `pipeline.run`. Everything is best-effort — a bug
here must never change whether the pipeline itself succeeded.
"""

from __future__ import annotations

import html
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
from sqlmodel import Session, col, select

from app.platform.logging import log
from pipeline.models import PipelineRun


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

HISTORY_WINDOW = 30  # runs of history the averages are computed over
STALE_RUN_HOURS = 26  # older than this with no success → "pipeline may be down"
YIELD_DROP_RATIO = 0.3  # inserted < 30% of average → yield-drop flag
MIN_AVG_FETCH_FOR_DOWN = 3.0  # only call "source down" if it normally fetches > this
MIN_AVG_INSERT_FOR_YIELD = 2.0  # ignore yield drops on sources that barely insert

# A single feed publisher fetches far less than the aggregate "Feeds" source,
# so it gets its own (much lower) bar for "this normally produces something".
MIN_AVG_FETCH_FOR_PUBLISHER_DOWN = 0.3

# Representative URL to probe when a source suddenly fetches nothing. Aggregate
# sources (Substack = many feeds) have no single URL, so they're omitted and the
# report just says so.
PROBE_URL_BY_SOURCE = {
    "Hacker News": "https://hacker-news.firebaseio.com/v0/topstories.json",
    "AI News": "https://news.smol.ai/rss.xml",
}


# ─── In-memory stats (populated during the run) ───────────────────────────────


@dataclass
class SourceStats:
    """Funnel counts for one source in one run. Every drop is accounted for:
    fetched → off-topic → known → dead → dup → below-threshold → inserted."""

    # `source` here is the run-level fetcher label (Hacker News / AI News /
    # Feeds), not a publisher — see `PublisherStats` below for per-publisher
    # granularity within "Feeds".
    source: str
    fetched: int = 0
    filtered_off_topic: int = 0
    filtered_known: int = 0
    filtered_dead: int = 0
    filtered_thin_repo: int = 0
    deduped: int = 0
    below_threshold: int = 0
    inserted: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class PublisherStats:
    """Fetch/insert counts for one publisher within the "Feeds" source in one
    run — the granularity ``SourceStats`` can't give, since "Feeds" aggregates
    every RSS/substack publisher under one label."""

    name: str
    fetched: int = 0
    inserted: int = 0
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
        fetched: list[dict],
        inserted: list[dict],
        errors: dict[str, str],
    ) -> None:
        """Record per-publisher fetch/insert counts for one source's run.

        ``expected_names`` is every publisher this source was supposed to
        poll, so a publisher that fetched nothing still gets a row (fetched=0)
        instead of silently disappearing from the stats.
        """
        fetched_counts: dict[str, int] = {}
        for a in fetched:
            fetched_counts[a["source"]] = fetched_counts.get(a["source"], 0) + 1
        inserted_counts: dict[str, int] = {}
        for a in inserted:
            inserted_counts[a["source"]] = inserted_counts.get(a["source"], 0) + 1

        for name in expected_names:
            self.publishers.append(
                PublisherStats(
                    name=name,
                    fetched=fetched_counts.get(name, 0),
                    inserted=inserted_counts.get(name, 0),
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


def _load_history(session: Session, exclude_started_at: datetime) -> list[dict]:
    """Last HISTORY_WINDOW runs (excluding the current one), newest first."""
    runs = session.exec(
        select(PipelineRun)
        .where(PipelineRun.started_at != exclude_started_at)
        .order_by(col(PipelineRun.started_at).desc())
        .limit(HISTORY_WINDOW)
    ).all()
    return [
        {"sources": r.sources, "publishers": r.publishers, "ok": r.ok} for r in runs
    ]


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


# ─── Anomaly detection (runs at the END of each run) ──────────────────────────


def verify_run(session: Session, stats: RunStats) -> None:
    """Compare this run to recent history; email a report every run (not just
    when something looks wrong) so a daily digest lands regardless."""
    history = _load_history(session, exclude_started_at=stats.started_at)

    anomalies: list[str] = []
    if not stats.ok:
        anomalies.append("Pipeline run did NOT complete (crashed mid-run).")
    for s in stats.sources:
        anomalies.extend(_check_source(s, history))
    for p in stats.publishers:
        anomalies.extend(_check_publisher(p, history))

    subject = (
        "Pipeline health: anomalies detected" if anomalies else "Pipeline run report"
    )
    _send_alert(subject=subject, body=_format_report(stats, anomalies, len(history)))
    log(f"  Verifier: {'anomalies detected' if anomalies else 'no anomalies'}")


def _check_source(s: SourceStats, history: list[dict]) -> list[str]:
    flags: list[str] = []

    if s.errors:
        shown = "; ".join(s.errors[:3])
        flags.append(f"{s.source}: {len(s.errors)} error(s) — {shown}")

    prev = _source_rows(history, s.source)
    avg_fetch = _avg(prev, "fetched")
    avg_insert = _avg(prev, "inserted")

    if avg_fetch is not None and avg_fetch > MIN_AVG_FETCH_FOR_DOWN and s.fetched == 0:
        flags.append(
            f"{s.source}: fetched 0 (30-run avg {avg_fetch:.1f}). "
            f"Probe: {_probe(s.source)}"
        )
    elif (
        avg_insert is not None
        and avg_insert >= MIN_AVG_INSERT_FOR_YIELD
        and s.inserted < YIELD_DROP_RATIO * avg_insert
    ):
        flags.append(
            f"{s.source}: inserted {s.inserted} (30-run avg {avg_insert:.1f}) "
            "— yield down >70%"
        )

    return flags


def _check_publisher(p: PublisherStats, history: list[dict]) -> list[str]:
    """Same idea as ``_check_source`` but one feed publisher at a time — this
    is what catches a single dead feed (e.g. a 403) that the aggregate
    "Feeds" numbers hide because every other feed is still healthy."""
    if p.error:
        return [f"{p.name}: fetch failed — {p.error}"]

    prev = _publisher_rows(history, p.name)
    avg_fetch = _avg(prev, "fetched")
    if (
        avg_fetch is not None
        and avg_fetch > MIN_AVG_FETCH_FOR_PUBLISHER_DOWN
        and p.fetched == 0
    ):
        return [
            f"{p.name}: fetched 0 (30-run avg {avg_fetch:.1f}) — no error, "
            "feed returned nothing this run"
        ]
    return []


def _source_rows(history: list[dict], label: str) -> list[dict]:
    rows: list[dict] = []
    for run in history:
        for src in run.get("sources", []):
            if src.get("source") == label:
                rows.append(src)
    return rows


def _publisher_rows(history: list[dict], name: str) -> list[dict]:
    rows: list[dict] = []
    for run in history:
        for pub in run.get("publishers", []):
            if pub.get("name") == name:
                rows.append(pub)
    return rows


def _avg(rows: list[dict], key: str) -> float | None:
    if not rows:
        return None
    return sum(r.get(key, 0) for r in rows) / len(rows)


def _probe(label: str) -> str:
    """HTTP GET the source URL to tell 'source is down' from 'our parser broke'."""
    url = PROBE_URL_BY_SOURCE.get(label)
    if not url:
        return "no probe URL (aggregate source)"
    try:
        r = httpx.get(url, timeout=10.0, follow_redirects=False)
        if r.is_redirect:
            return f"redirecting ({r.status_code} → {r.headers.get('location', '?')})"
        if r.status_code == 200:
            return "URL alive (200) — likely our parser, not the source"
        return f"HTTP {r.status_code}"
    except Exception as e:
        return f"unreachable ({type(e).__name__})"


def _format_report(stats: RunStats, anomalies: list[str], history_len: int) -> str:
    lines: list[str] = []
    if anomalies:
        lines += ["ANOMALIES", "========="]
        lines += [f"  - {a}" for a in anomalies]
        lines.append("")
    else:
        lines += ["No anomalies detected.", ""]
    lines += ["THIS RUN", "========"]
    for s in stats.sources:
        row = (
            f"  {s.source}: fetched {s.fetched} "
            f"→ off-topic -{s.filtered_off_topic} "
            f"→ known -{s.filtered_known} "
            f"→ dead -{s.filtered_dead} "
            f"→ thin-repo -{s.filtered_thin_repo} "
            f"→ dup -{s.deduped} "
            f"→ below-threshold -{s.below_threshold} "
            f"→ inserted {s.inserted}"
        )
        if s.errors:
            row += f"   [errors: {len(s.errors)}]"
        lines.append(row)
    dur = f"{stats.duration_ms / 1000:.0f}s" if stats.duration_ms else "?"
    lines += [
        "",
        f"Run {'OK' if stats.ok else 'CRASHED'} in {dur}. "
        f"{history_len} prior runs in history.",
    ]
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
