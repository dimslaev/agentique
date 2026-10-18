"""The nightly collect run and the daily mail, the two verbs the timers call.

Orchestration only: each step (`fetch`, `filter`, `queue`) owns its own logging
and commits. This file's job is the funnel: for every source, run the steps in
order, record the counts, and make sure one bad source cannot take the others
down with it.

The funnel ends at `queue_candidates`: every survivor is written as a pending
candidate and nothing is scored, summarized or inserted. The curation agent
reads those candidates an hour later and decides what becomes an Article — see
docs/adr/0009-agent-curation.md.
"""

from __future__ import annotations

import sys

from sqlmodel import Session

from app.core.db.engine import engine
from app.core.email import send_mail
from app.core.logging import log, short_error
from app.features.collect.fetch import build_sources, fetch_source, resolve_publishers
from app.features.collect.filter import filter_known_urls
from app.features.collect.model import Candidate, RunStats
from app.features.collect.publishers import PublisherResolver
from app.features.collect.queue import queue_candidates
from app.features.collect.report import format_night, read_night, subject
from app.features.collect.runs import record_new, record_polled, record_run


def run(stats: RunStats) -> None:
    """One pass over every source, counted into ``stats``."""
    log("=== Pipeline start ===")

    with Session(engine) as session:
        resolver = PublisherResolver(session=session)

        for source in build_sources(session):
            log(f"\n=== Processing {source.label} ===")
            s = stats.source(source.label)

            # Held outside the try so the publisher bookkeeping below survives
            # a failure in any step after the fetch.
            fetch_errors: dict[str, str] = {}
            queued: list[Candidate] = []
            fetched_ok = False

            try:
                fetched, fetch_errors = fetch_source(source)
                fetched_ok = True
                s.fetched = len(fetched)

                # The only gate: a URL already judged, or already waiting, is
                # not queued twice. Topic, reach and duplicates are the agent's
                # call (ADR 11). Ahead of resolving publishers, so a link seen
                # before never costs a lookup or creates one.
                fresh = filter_known_urls(session, fetched, source.label)

                candidates = resolve_publishers(fresh, resolver)

                # The end of the funnel: the agent is the judge, so the run
                # stops at a pending row.
                queued = queue_candidates(session, candidates)
                s.queued = len(queued)
            except Exception as e:
                # One source failing must not sink the others — record and move
                # on. The message is truncated: a BAML failure carries every
                # attempt's prompt and the upstream's HTML, and this string is
                # stored in pipeline_run and emailed.
                message = short_error(e)
                s.error = message
                log(f"  !! {source.label} failed: {message}")
                session.rollback()
            finally:
                # Whatever happened after the fetch, the publishers it polled
                # get stamped: on 2026-09-03 a failure after the fetch took the
                # per-publisher record with it on exactly the night something
                # was wrong. A fetch that itself failed stamps nothing — there
                # was no answer to record. Best-effort: bookkeeping never fails
                # a source.
                try:
                    if fetched_ok and source.publisher_names:
                        record_polled(session, source.publisher_names, fetch_errors)
                    record_new(session, (a["publisher_id"] for a in queued))
                except Exception as e:
                    log(f"  Publisher bookkeeping failed: {short_error(e)}")
                    session.rollback()

        if resolver.quarantined:
            log(
                f"\n{len(resolver.quarantined)} publisher(s) quarantined this run: "
                f"{', '.join(resolver.quarantined)}"
            )
        if resolver.created:
            log(
                f"\n{len(resolver.created)} publisher(s) created for new sites: "
                f"{', '.join(resolver.created)}"
            )

    log("=== Pipeline complete ===")


def run_nightly() -> int:
    """The whole nightly run: collect, then record it. Returns the exit code.

    No email from here. The daily mail (`send_report`) reads the recorded row
    after the curation session: a crashed run, or no run at all, is the first
    thing it says. Recording is best-effort and never flips the exit code.
    """
    stats = RunStats()
    crashed: Exception | None = None
    try:
        run(stats)
    except Exception as e:
        crashed = e
        print(f"Pipeline failed: {e}", file=sys.stderr)

    stats.finish(ok=crashed is None)

    try:
        with Session(engine) as session:
            record_run(session, stats)
    except Exception as e:
        print(f"Recording the run failed: {e}", file=sys.stderr)

    return 1 if crashed else 0


def send_report() -> int:
    """Read the night out of the database and mail it. Returns the exit code."""
    try:
        with Session(engine) as session:
            night = read_night(session)
        send_mail(subject(night), format_night(night))
    except Exception as e:
        print(f"Daily report failed: {e}", file=sys.stderr)
        return 1
    return 0
