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
from pipeline.health import RunStats, check_liveness, record_run, report_run
from pipeline.publishers import PublisherResolver
from pipeline.steps.fetch import build_sources, fetch_source, resolve_publishers
from pipeline.steps.filter import filter_known_urls
from pipeline.steps.queue import queue_candidates
from pipeline.types import RawItem


def run_pipeline(stats: RunStats) -> None:
    log("=== Pipeline start ===")

    with Session(get_engine()) as session:
        resolver = PublisherResolver(session=session)

        for source in build_sources(session):
            log(f"\n=== Processing {source.label} ===")
            s = stats.source(source.label)

            # Held outside the try so the publisher stats below survive a
            # failure in any step after the fetch.
            fetched: list[RawItem] = []
            fetch_errors: dict[str, str] = {}
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
                s.filtered_known = len(candidates) - len(fresh)

                # The end of the funnel: the agent is the judge, so the run
                # stops at a pending row.
                s.queued = len(queue_candidates(session, fresh))
            except Exception as e:
                # One source failing must not sink the others — record and move
                # on. The message is truncated: a BAML failure carries every
                # attempt's prompt and the upstream's HTML, and this string is
                # stored in pipeline_run and emailed.
                message = short_error(e)
                s.errors.append(message)
                log(f"  !! {source.label} failed: {message}")
                session.rollback()
            finally:
                # Per-publisher health is recorded whatever happened after the
                # fetch. It used to sit mid-try, so the 2026-09-03 scoring
                # failure took it with it and 99 feeds dropped out of the run's
                # stats on exactly the night something was wrong. A fetch that
                # itself failed records nothing: there are no counts to report.
                if fetched_ok and source.publisher_names:
                    stats.record_publishers(
                        source.publisher_names, fetched, fetch_errors
                    )

        if resolver.quarantined:
            log(
                f"\n{len(resolver.quarantined)} publisher(s) quarantined this run: "
                f"{', '.join(resolver.quarantined)}"
            )

    log("=== Pipeline complete ===")


# ─── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Dead-man's-switch: did last night's run die silently? (best-effort)
    try:
        with Session(get_engine()) as session:
            check_liveness(session)
    except Exception as e:
        print(f"Liveness check failed: {e}", file=sys.stderr)

    stats = RunStats()
    crashed: Exception | None = None
    try:
        run_pipeline(stats)
    except Exception as e:
        crashed = e
        print(f"Pipeline failed: {e}", file=sys.stderr)

    stats.finish(ok=crashed is None)

    # Record stats, and email only what cannot wait. Best-effort: never flips
    # the exit code.
    try:
        with Session(get_engine()) as session:
            record_run(session, stats)
        # This run has landed nothing yet, so its report would be a page of
        # counts an hour before the articles exist. The night's one email goes
        # out after the agent has read the candidates (`python -m
        # pipeline.report`). A crash does not wait for that.
        if not stats.ok:
            report_run(stats)
    except Exception as e:
        print(f"Health recording/report failed: {e}", file=sys.stderr)

    sys.exit(1 if crashed else 0)
