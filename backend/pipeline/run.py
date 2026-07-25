"""Pipeline entry point. Run with: python -m pipeline.run

Orchestration only — each step lives in pipeline.steps.* and owns its own
logging and commits. This file's job is the funnel: for every source, run the
steps in order, record the counts, and make sure one bad source cannot take the
others down with it.
"""

from __future__ import annotations

import sys

from sqlmodel import Session

from pipeline.db import get_engine
from pipeline.health import RunStats, check_liveness, record_run, verify_run
from pipeline.publishers import PublisherResolver
from pipeline.steps.enrich import (
    assign_tags,
    embed_articles,
    improve_titles,
    summarize_and_categorize,
)
from pipeline.steps.fetch import build_sources, fetch_source, resolve_publishers
from pipeline.steps.filter import dedup_semantic, filter_dead_domains, filter_known_urls
from pipeline.steps.persist import insert_articles
from pipeline.steps.score import prefilter_keep_drop, score_articles
from pipeline.tags import load_vocabulary
from pipeline.utils import log


def run_pipeline(stats: RunStats) -> None:
    log("=== Pipeline start ===")

    with Session(get_engine()) as session:
        resolver = PublisherResolver(session=session)
        vocab = load_vocabulary(session)

        for source in build_sources(session):
            log(f"\n=== Processing {source.label} ===")
            s = stats.source(source.label)

            try:
                fetched = fetch_source(source)
                s.fetched = len(fetched)

                resolve_publishers(fetched, resolver)

                fresh = filter_known_urls(session, fetched, source.label)
                s.filtered_known = s.fetched - len(fresh)

                alive = filter_dead_domains(fresh, source.label)
                s.filtered_dead = len(fresh) - len(alive)

                # Pre-filter obvious junk before the dedup LLM call: cuts the
                # new-article side dedup has to check, and junk-that-is-a-dup
                # gets recorded in ScoredUrl instead of silently dropped by
                # dedup.
                candidates = prefilter_keep_drop(session, alive)
                prefiltered = len(alive) - len(candidates)

                unique = dedup_semantic(session, candidates, source.label)
                s.deduped = len(candidates) - len(unique)

                scored = score_articles(session, unique)
                # below_threshold = pre-filter drops + LLM sub-threshold
                s.below_threshold = prefiltered + (len(unique) - len(scored))

                inserted = insert_articles(session, scored)
                s.inserted = len(inserted)

                improve_titles(session, inserted)
                processed = summarize_and_categorize(session, inserted)
                assign_tags(session, processed, vocab)
                embed_articles(session, processed)
            except Exception as e:
                # One source failing must not sink the others — record and move on.
                s.errors.append(f"{type(e).__name__}: {e}")
                log(f"  !! {source.label} failed: {e}")
                session.rollback()

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

    # Record stats + run the verifier. Best-effort: never flips the exit code.
    try:
        with Session(get_engine()) as session:
            record_run(session, stats)
            verify_run(session, stats)
    except Exception as e:
        print(f"Health recording/verify failed: {e}", file=sys.stderr)

    sys.exit(1 if crashed else 0)
