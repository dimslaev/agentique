"""The daily mail. Run with: python -m pipeline.report

Sent after the curation session, not after the fetch: the 04:00 run queues
candidates and lands nothing, so a mail at that hour would be a page of counts
an hour before the articles exist. Everything in it is read from the database,
so the mail needs nothing from the run that it is reporting on — which is what
lets it say the run never happened.

What it says, in order of what a reader acts on:

- the run crashed, or has not finished one in ``STALE_RUN_HOURS`` (liveness);
- sources that fetched nothing in the last run;
- publishers whose last fetch failed (``Publisher.last_error``);
- what got published, and how much is still waiting.

A publisher that has gone quiet is deliberately not here: most quiet feeds are
just quiet, and a mail that lists them every day stops being read.
``Publisher.last_new_at`` answers that when someone asks.
"""

from __future__ import annotations

import html
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, col, func, select

from app.catalog.models import Article, Publisher
from app.platform.logging import log
from pipeline.db import get_engine
from pipeline.models import PipelineRun, Reject, RejectStage

# Older than this with no successful run: "pipeline may be down".
STALE_RUN_HOURS = 26
# How far back the mail looks. One window covers the 04:00 run and the 05:00
# curation session together, which is the night a reader is asking about.
REPORT_WINDOW_HOURS = 24


@dataclass(frozen=True)
class Landed:
    title: str
    url: str
    score: int
    publisher: str


@dataclass(frozen=True)
class Night:
    """One night, read out of the database."""

    liveness: str | None
    silent_sources: list[str]
    source_errors: list[str]
    failing_publishers: list[tuple[str, str]]
    landed: list[Landed]
    rejected: int
    still_pending: int


def liveness(last: PipelineRun | None, now: datetime) -> str | None:
    """What is wrong with the last run, or None when nothing is. Pure."""
    if last is None or last.finished_at is None:
        return "No pipeline run is recorded."
    age = now - last.finished_at
    if age > timedelta(hours=STALE_RUN_HOURS):
        return (
            f"No pipeline run in {age.total_seconds() / 3600:.0f}h "
            f"(last: {last.finished_at:%Y-%m-%d %H:%M} UTC). The pipeline "
            "container or its schedule is broken."
        )
    if not last.ok:
        return f"The last run crashed ({last.finished_at:%Y-%m-%d %H:%M} UTC)."
    return None


def source_lines(sources: list[dict]) -> tuple[list[str], list[str]]:
    """``(silent, errors)`` from a run's stored per-source counts. Pure.

    Tolerates the older, longer shape and the ``errors`` list it carried, so a
    run recorded before this one still reports.
    """
    silent: list[str] = []
    errors: list[str] = []
    for s in sources:
        name = str(s.get("source", "?"))
        if not s.get("fetched"):
            silent.append(name)
        error = s.get("error")
        for e in [error] if error else s.get("errors") or []:
            errors.append(f"{name}: {e}")
    return silent, errors


def read_night(session: Session, now: datetime | None = None) -> Night:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=REPORT_WINDOW_HOURS)

    last = session.exec(
        select(PipelineRun).order_by(col(PipelineRun.started_at).desc())
    ).first()
    silent, errors = source_lines(last.sources if last else [])

    failing = session.exec(
        select(Publisher.name, Publisher.last_error)
        .where(
            col(Publisher.is_active).is_(True),
            col(Publisher.last_error).is_not(None),
        )
        .order_by(col(Publisher.name))
    ).all()

    landed = session.exec(
        select(Article, Publisher)
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id), isouter=True)
        .where(col(Article.created_at) >= cutoff)
        .order_by(col(Article.score).desc())
    ).all()

    # Counted over what this window queued: a reject keeps the `created_at` of
    # the night its candidate was written.
    rejected = session.exec(
        select(func.count())
        .select_from(Reject)
        .where(
            col(Reject.stage) == RejectStage.below_threshold,
            col(Reject.created_at) >= cutoff,
        )
    ).one()
    still_pending = session.exec(
        select(func.count())
        .select_from(Reject)
        .where(col(Reject.stage) == RejectStage.pending)
    ).one()

    return Night(
        liveness=liveness(last, now),
        silent_sources=silent,
        source_errors=errors,
        failing_publishers=[(name, error or "") for name, error in failing],
        landed=[
            Landed(
                title=a.title, url=a.url, score=a.score, publisher=p.name if p else ""
            )
            for a, p in landed
        ],
        rejected=rejected,
        still_pending=still_pending,
    )


def subject(night: Night) -> str:
    if night.liveness:
        return "Pipeline needs a look"
    return (
        f"{len(night.landed)} article(s) landed" if night.landed else "Nothing landed"
    )


def format_night(night: Night) -> str:
    lines: list[str] = []
    if night.liveness:
        lines += ["PIPELINE", "========", f"  {night.liveness}", ""]

    problems = [f"  {name} fetched nothing." for name in night.silent_sources]
    problems += [f"  {e}" for e in night.source_errors]
    problems += [f"  {name}: {error}" for name, error in night.failing_publishers]
    if problems:
        lines += ["NEEDS A LOOK", "============", *problems, ""]

    heading = f"LANDED ({len(night.landed)})"
    lines += [heading, "=" * len(heading)]
    if night.landed:
        for a in night.landed:
            byline = f" — {a.publisher}" if a.publisher else ""
            lines.append(f"  [{a.score}/100] {a.title}{byline}")
            lines.append(f"    {a.url}")
    else:
        lines.append("  Nothing was published. If that is not what you expected,")
        lines.append("  the curation session is the first thing to check.")

    lines.append("")
    lines.append(f"{night.rejected} turned down.")
    lines.append(
        f"{night.still_pending} candidate(s) still waiting on a verdict."
        if night.still_pending
        else "Queue empty — every candidate got a verdict."
    )
    return "\n".join(lines)


def send_mail(subject_line: str, body: str) -> None:
    """Email through Resend, or log the mail when the environment has no key.
    Best-effort: a failed send is logged, never raised."""
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("EMAILS_FROM_EMAIL")
    to_email = os.environ.get("PIPELINE_ALERT_EMAIL") or from_email
    project = os.environ.get("PROJECT_NAME") or "Agentique"
    if not (api_key and from_email and to_email):
        log(f"  [mail suppressed — email env not set] {subject_line}\n{body}")
        return
    try:
        import resend

        resend.api_key = api_key
        resend.Emails.send(
            {
                "from": f"{project} pipeline <{from_email}>",
                "to": to_email,
                "subject": f"[{project}] {subject_line}",
                "html": f"<pre>{html.escape(body)}</pre>",
            }
        )
        log(f"  Mail sent to {to_email}: {subject_line}")
    except Exception as e:
        log(f"  Mail send failed: {e}")


if __name__ == "__main__":
    try:
        with Session(get_engine()) as session:
            night = read_night(session)
        send_mail(subject(night), format_night(night))
    except Exception as e:
        print(f"Daily report failed: {e}", file=sys.stderr)
        sys.exit(1)
