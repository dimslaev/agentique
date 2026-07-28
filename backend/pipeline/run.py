"""Pipeline entry point. Run with: python -m pipeline.run

Orchestration only — each step lives in pipeline.steps.* and owns its own
logging and commits. This file's job is the funnel: for every source, run the
steps in order, record the counts, and make sure one bad source cannot take the
others down with it.

The funnel is ordered cheapest-first, and every gate in it answers a narrower
question than the one before:

    fetch      poll the source, fill content, resolve the publisher
    known      have we seen this URL?                        (db)
    dead       does the domain resolve?                      (dns)
    gate 0     is this AI developer news at all?             (numpy)
    gate 1     is it near any category we cover?             (numpy)
    dedup      do we already carry this story?               (llm)
    gate 2     which categories, specifically?               (llm)
    insert     store it, with the categories that admitted it

An article that matches no category is never stored. That is the whole
editorial policy — there is no score, and no "keep it around in case".
"""

from __future__ import annotations

import sys

from sqlmodel import Session

from pipeline.categories import load_vocabulary
from pipeline.db import get_engine
from pipeline.health import RunStats, check_liveness, record_run, verify_run
from pipeline.publishers import PublisherResolver
from pipeline.steps.categorize import (
    match_categories,
    prefilter_categories,
    prefilter_keep_drop,
)
from pipeline.steps.enrich import embed_articles, improve_titles, summarize
from pipeline.steps.fetch import build_sources, fetch_source, resolve_publishers
from pipeline.steps.filter import dedup_semantic, filter_dead_domains, filter_known_urls
from pipeline.steps.persist import insert_articles
from pipeline.utils import log


def run_pipeline(stats: RunStats) -> None:
    log("=== Pipeline start ===")

    with Session(get_engine()) as session:
        resolver = PublisherResolver(session=session)
        # Raises on an empty category table: with no vocabulary nothing can
        # match, and the run would quietly store zero articles all night.
        vocab = load_vocabulary(session)
        log(f"Loaded {len(vocab.slugs)} categories: {', '.join(vocab.slugs_ordered)}")

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

                # Both static gates run before the dedup LLM call: they cut the
                # new-article side dedup has to check, and an off-topic item
                # that is also a dupe gets recorded in ScoredUrl instead of
                # silently vanishing into dedup.
                kept = prefilter_keep_drop(session, alive)
                on_topic = prefilter_categories(session, kept, vocab)
                gated = len(alive) - len(on_topic)

                unique = dedup_semantic(session, on_topic, source.label)
                s.deduped = len(on_topic) - len(unique)

                matched = match_categories(session, unique, vocab)
                # unmatched = static-gate drops + articles the matcher rejected
                s.unmatched = gated + (len(unique) - len(matched))

                inserted = insert_articles(session, matched, vocab)
                s.inserted = len(inserted)

                improve_titles(session, inserted)
                processed = summarize(session, inserted)
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
