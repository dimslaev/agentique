"""Pipeline entry point. Run with: python -m pipeline.run

Orchestration only — each step lives in pipeline.steps.* and owns its own
logging and commits. This file's job is the funnel: for every source, run the
steps in order, record the counts, and make sure one bad source cannot take the
others down with it.

The funnel ends at `queue_candidates`: every survivor is written as a pending
candidate and nothing is scored, summarized or inserted. The curation agent
reads those candidates an hour later and decides what becomes an Article — see
docs/adr/0009-agent-curation.md.
"""

from __future__ import annotations

import sys

from sqlmodel import Session

from app.platform.logging import log, short_error
from pipeline.db import get_engine
from pipeline.publishers import PublisherResolver
from pipeline.runs import RunStats, record_new, record_polled, record_run
from pipeline.steps.fetch import build_sources, fetch_source, resolve_publishers
from pipeline.steps.filter import filter_known_urls
from pipeline.steps.queue import queue_candidates
from pipeline.types import Candidate


def run_pipeline(stats: RunStats) -> None:
    log("=== Pipeline start ===")

    with Session(get_engine()) as session:
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

                candidates = resolve_publishers(fetched, resolver)

                # The only gate: a URL already judged, or already waiting, is
                # not queued twice. Topic, reach and duplicates are the agent's
                # call (ADR 11).
                fresh = filter_known_urls(session, candidates, source.label)

                # The end of the funnel: the agent is the judge, so the run
                # stops at a pending row.
                queued = queue_candidates(session, fresh)
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

    log("=== Pipeline complete ===")


# ─── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    stats = RunStats()
    crashed: Exception | None = None
    try:
        run_pipeline(stats)
    except Exception as e:
        crashed = e
        print(f"Pipeline failed: {e}", file=sys.stderr)

    stats.finish(ok=crashed is None)

    # No email from here. The daily mail (`python -m pipeline.report`) reads
    # this row after the curation session: a crashed run, or no run at all, is
    # the first thing it says. Best-effort: never flips the exit code.
    try:
        with Session(get_engine()) as session:
            record_run(session, stats)
    except Exception as e:
        print(f"Recording the run failed: {e}", file=sys.stderr)

    sys.exit(1 if crashed else 0)
