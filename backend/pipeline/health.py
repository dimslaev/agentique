"""Pipeline health: capture per-run stats, detect anomalies, alert by email.

Runs in-process at the end of `pipeline.run`. Everything is best-effort — a bug
here must never change whether the pipeline itself succeeded. Reads config from
`os.environ` directly (like `run.py`), not `app.core.config.settings`, so it
stays decoupled from the backend's full Settings object.
"""

from __future__ import annotations

import html
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta

import httpx
from sqlmodel import Session, col, select

from app.models_agentique import PipelineRun
from pipeline.utils import log

# ─── Tunables ─────────────────────────────────────────────────────────────────

HISTORY_WINDOW = 30  # runs of history the averages are computed over
STALE_RUN_HOURS = 26  # older than this with no success → "pipeline may be down"
YIELD_DROP_RATIO = 0.3  # inserted < 30% of average → yield-drop flag
MIN_AVG_FETCH_FOR_DOWN = 3.0  # only call "source down" if it normally fetches > this
MIN_AVG_INSERT_FOR_YIELD = 2.0  # ignore yield drops on sources that barely insert

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
    fetched → known → dead → dup → below-threshold → inserted."""

    source: str
    fetched: int = 0
    filtered_known: int = 0
    filtered_dead: int = 0
    deduped: int = 0
    below_threshold: int = 0
    inserted: int = 0
    errors: list[str] = field(default_factory=list)


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


# ─── Persistence ──────────────────────────────────────────────────────────────


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


def _load_history(session: Session, exclude_started_at: datetime) -> list[dict]:
    """Last HISTORY_WINDOW runs (excluding the current one), newest first."""
    runs = session.exec(
        select(PipelineRun)
        .where(PipelineRun.started_at != exclude_started_at)
        .order_by(col(PipelineRun.started_at).desc())
        .limit(HISTORY_WINDOW)
    ).all()
    return [{"sources": r.sources, "ok": r.ok} for r in runs]


# ─── Dead-man's-switch (runs at the START of each run) ─────────────────────────


def check_liveness(session: Session) -> None:
    """Alert if there hasn't been a successful run in STALE_RUN_HOURS.

    Catches the case where a previous night's run died so hard it recorded
    nothing. Runs on the next invocation because supercronic itself is long-lived.
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
    """Compare this run to recent history; email if anything looks wrong."""
    history = _load_history(session, exclude_started_at=stats.started_at)

    anomalies: list[str] = []
    if not stats.ok:
        anomalies.append("Pipeline run did NOT complete (crashed mid-run).")
    for s in stats.sources:
        anomalies.extend(_check_source(s, history))

    if anomalies:
        _send_alert(
            subject="Pipeline health: anomalies detected",
            body=_format_report(stats, anomalies, len(history)),
        )
    else:
        log("  Verifier: no anomalies")


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


def _source_rows(history: list[dict], label: str) -> list[dict]:
    rows: list[dict] = []
    for run in history:
        for src in run.get("sources", []):
            if src.get("source") == label:
                rows.append(src)
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
    lines = ["ANOMALIES", "========="]
    lines += [f"  - {a}" for a in anomalies]
    lines += ["", "THIS RUN", "========"]
    for s in stats.sources:
        row = (
            f"  {s.source}: fetched {s.fetched} "
            f"→ known -{s.filtered_known} "
            f"→ dead -{s.filtered_dead} "
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


# ─── Email (Resend, via os.environ — no Settings import) ──────────────────────


def _send_alert(subject: str, body: str) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("EMAILS_FROM_EMAIL")
    to_email = os.environ.get("PIPELINE_ALERT_EMAIL") or from_email

    if not (api_key and from_email and to_email):
        log(f"  [alert suppressed — email env not set] {subject}\n{body}")
        return

    name = os.environ.get("PROJECT_NAME") or "Agentique"
    try:
        import resend

        resend.api_key = api_key
        resend.Emails.send(
            {
                "from": f"{name} pipeline <{from_email}>",
                "to": to_email,
                "subject": f"[{name}] {subject}",
                "html": f"<pre>{html.escape(body)}</pre>",
            }
        )
        log(f"  Alert emailed to {to_email}: {subject}")
    except Exception as e:
        log(f"  Alert send failed: {e}")
