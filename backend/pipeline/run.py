"""Pipeline entry point. Run with: python -m pipeline.run

Orchestration only — each step lives in pipeline.steps.* and owns its own
logging and commits. This file's job is the funnel: for every source, run the
steps in order, record the counts, and make sure one bad source cannot take the
others down with it.
"""

from __future__ import annotations

import sys

from sqlmodel import Session

from app.platform.logging import log, short_error
from pipeline.db import get_engine
from pipeline.health import RunStats, check_liveness, record_run, report_run
from pipeline.publishers import PublisherResolver
from pipeline.steps.enrich import (
    categorize_and_tag_articles,
    embed_articles,
    improve_titles,
)
from pipeline.steps.fetch import (
    build_sources,
    drop_off_topic,
    fetch_source,
    resolve_publishers,
)
from pipeline.steps.filter import (
    dedup_semantic,
    filter_dead_domains,
    filter_known_urls,
    filter_thin_repos,
)
from pipeline.steps.persist import insert_articles
from pipeline.steps.score import prefilter_keep_drop, score_articles
from pipeline.steps.summarize import summarize_articles
from pipeline.tags import load_vocabulary
from pipeline.types import Persisted, RawItem


def run_pipeline(stats: RunStats) -> None:
    log("=== Pipeline start ===")

    with Session(get_engine()) as session:
        resolver = PublisherResolver(session=session)
        vocab = load_vocabulary(session)

        for source in build_sources(session):
            log(f"\n=== Processing {source.label} ===")
            s = stats.source(source.label)

            # Held outside the try so the publisher stats below survive a
            # failure in any step after the fetch.
            fetched: list[RawItem] = []
            fetch_errors: dict[str, str] = {}
            inserted: list[Persisted] = []
            fetched_ok = False

            try:
                fetched, fetch_errors = fetch_source(source)
                fetched_ok = True
                s.fetched = len(fetched)

                candidates = resolve_publishers(fetched, resolver)

                # First gate, and the cheapest: a title regex on the broad
                # publishers. Ahead of every DB, DNS, embedding and LLM cost
                # below, so an off-topic post from a gated feed costs nothing.
                on_topic = drop_off_topic(candidates, source.label)
                s.filtered_off_topic = s.fetched - len(on_topic)

                fresh = filter_known_urls(session, on_topic, source.label)
                s.filtered_known = len(on_topic) - len(fresh)

                alive = filter_dead_domains(fresh, source.label)
                s.filtered_dead = len(fresh) - len(alive)

                # A repo nobody has starred is noise whichever source linked it,
                # and one API call settles it — cheaper than the embedding and
                # scoring calls below, so it goes ahead of them.
                real = filter_thin_repos(session, alive, source.label)
                s.filtered_thin_repo = len(alive) - len(real)

                # Pre-filter obvious junk before the scoring LLM call: cuts what
                # the scorer has to see, and junk gets recorded as a reject
                # instead of silently dropped.
                worth_scoring = prefilter_keep_drop(session, real)
                prefiltered = len(real) - len(worth_scoring)

                # Before scoring: a story we already carry must never cost an
                # LLM call. Runs after the pre-filter so junk that is also a
                # dup is recorded as junk, the verdict that says more.
                unique = dedup_semantic(session, worth_scoring, source.label)
                s.deduped = len(worth_scoring) - len(unique)

                scored = score_articles(session, unique)
                # below_threshold = pre-filter drops + LLM sub-threshold
                s.below_threshold = prefiltered + (len(unique) - len(scored))

                # Before the insert, not in enrichment: an article the model
                # cannot summarize is never inserted without a summary.
                summarized = summarize_articles(session, scored)
                s.unsummarized = len(scored) - len(summarized)

                inserted = insert_articles(session, summarized)
                s.inserted = len(inserted)

                improve_titles(session, inserted)
                processed = categorize_and_tag_articles(session, inserted, vocab)
                embed_articles(session, processed)
            except Exception as e:
                # One source failing must not sink the others — record and move
                # on. The message is truncated: a BAML failure carries every
                # attempt's prompt and the upstream's HTML, and this string is
                # stored in pipeline_run and emailed with the run report.
                message = short_error(e)
                s.errors.append(message)
                log(f"  !! {source.label} failed: {message}")
                session.rollback()
            finally:
                # Recorded here, not beside the insert, so the titles are the
                # rewritten ones: improve_titles edits each item in place, and
                # a failure in enrichment must still leave the run reporting
                # what it inserted.
                s.record_articles(inserted)

                # Per-publisher health is recorded whatever happened after the
                # fetch. It used to sit mid-try, so the 2026-09-03 scoring
                # failure took it with it and 99 feeds dropped out of the run's
                # stats on exactly the night something was wrong. A fetch that
                # itself failed records nothing: there are no counts to report.
                if fetched_ok and source.publisher_names:
                    stats.record_publishers(
                        source.publisher_names, fetched, inserted, fetch_errors
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

    # Record stats + email the report. Best-effort: never flips the exit code.
    try:
        with Session(get_engine()) as session:
            record_run(session, stats)
        report_run(stats)
    except Exception as e:
        print(f"Health recording/report failed: {e}", file=sys.stderr)

    sys.exit(1 if crashed else 0)
