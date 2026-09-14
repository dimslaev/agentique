"""Rescore every article from its title and summary, and mark the low ones.

One-off, not part of pipeline/run.py. The nightly run scores before it
summarizes, so it only ever judges a title and a 200-char snippet. This runs the
same ScoreArticles prompt on title + summary instead, and writes the new score,
the scorer's reason and ``rescored_at``. An article that now scores under the
pipeline's threshold also gets ``marked_for_deletion_at``; nothing is deleted.

A dry run by default: it scores and prints only the totals, writing nothing;
each verdict is in BAML's own log. --write persists, and resumes: it picks
articles where ``rescored_at`` is null and commits after every batch, so a
Ctrl-C, a crash or a provider outage costs at most the batch in flight. Run it
again and it carries on.

    cd backend && uv run --env-file ../.env python -m scripts.rescore_articles --limit 10
    cd backend && uv run --env-file ../.env python -m scripts.rescore_articles --write
    cd backend && uv run --env-file ../.env python -m scripts.rescore_articles --write --model gpt-oss-20b

Articles with no summary are skipped and counted: on a title alone the rubric
caps them at 70, a different test from everyone else's. To rescore everything
again, e.g. with the other model: ``UPDATE article SET rescored_at = NULL``.
"""

from __future__ import annotations

import argparse
import sys

from sqlmodel import Session, col, func, or_, select

from app.catalog.models import Article, Publisher
from app.platform.dates import get_datetime_utc
from app.platform.db import engine
from app.platform.logging import short_error, wait_ms
from baml_client.types import ArticleInput
from pipeline.llm_text import sanitize_llm_text
from pipeline.steps.score import (
    CURATED_INDIVIDUAL_THRESHOLD,
    SCORE_BATCH,
    SCORE_BATCH_PAUSE_MS,
    SCORE_THRESHOLD,
    threshold_for,
)
from scripts.rescoring import (
    DEFAULT_MODEL,
    MAX_FAILED_BATCHES_IN_A_ROW,
    MODELS,
    score_batch,
)

DRY_RUN_LIMIT = 10


def count_pending(session: Session) -> tuple[int, int]:
    """(articles still to rescore, articles skipped for having no summary)."""
    pending = session.exec(
        select(func.count())
        .select_from(Article)
        .where(col(Article.rescored_at).is_(None))
        .where(col(Article.summary).is_not(None), col(Article.summary) != "")
    ).one()
    no_summary = session.exec(
        select(func.count())
        .select_from(Article)
        .where(or_(col(Article.summary).is_(None), col(Article.summary) == ""))
    ).one()
    return pending, no_summary


def pick_batch(
    session: Session, after_id: int, size: int
) -> list[tuple[Article, Publisher]]:
    """The next unrescored articles past ``after_id``. Walking forward by id,
    rather than re-querying from the start, keeps a batch that failed this run
    from being picked again until the next run."""
    stmt = (
        select(Article, Publisher)
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .where(col(Article.rescored_at).is_(None))
        .where(col(Article.summary).is_not(None), col(Article.summary) != "")
        .where(col(Article.id) > after_id)
        .order_by(col(Article.id))
        .limit(size)
    )
    return list(session.exec(stmt).all())


def to_input(article: Article, publisher: Publisher) -> ArticleInput:
    return ArticleInput(
        url=article.url,
        title=article.title,
        source=publisher.name,
        snippet=article.summary,
        trust=str(publisher.trust),
        # When it was ingested, not today: "old" means old when we picked it up.
        seen_on=article.created_at.date().isoformat(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model", choices=sorted(MODELS), default=DEFAULT_MODEL)
    parser.add_argument(
        "--limit",
        type=int,
        help=f"articles to rescore this run (default: all with --write, "
        f"{DRY_RUN_LIMIT} without)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="persist scores and marks (default: dry run)",
    )
    args = parser.parse_args()
    write: bool = args.write
    model: str = args.model
    limit: int | None = args.limit
    if limit is None and not write:
        limit = DRY_RUN_LIMIT

    after_id = 0
    taken = rescored = marked = unanswered = 0
    failed_in_a_row = 0
    with Session(engine) as session:
        pending, no_summary = count_pending(session)
        mode = "writing" if write else "dry run, nothing is written"
        print(
            f"{pending} articles to rescore with {model} ({mode}); "
            f"{no_summary} skipped for having no summary"
        )
        total = pending if limit is None else min(pending, limit)
        try:
            while limit is None or taken < limit:
                size = SCORE_BATCH if limit is None else min(SCORE_BATCH, limit - taken)
                rows = pick_batch(session, after_id, size)
                if not rows:
                    break
                after_id = max(a.id or 0 for a, _ in rows)
                taken += len(rows)

                try:
                    verdicts = score_batch([to_input(a, p) for a, p in rows], model)
                except Exception as e:
                    failed_in_a_row += 1
                    print(
                        f"  batch failed ({failed_in_a_row} in a row), left for the "
                        f"next run: {short_error(e)}"
                    )
                    if failed_in_a_row >= MAX_FAILED_BATCHES_IN_A_ROW:
                        print("The provider looks down. Stopping; run again to resume.")
                        return 1
                    continue
                failed_in_a_row = 0

                now = get_datetime_utc()
                for article, publisher in rows:
                    verdict = verdicts.get(article.url)
                    if verdict is None:
                        unanswered += 1
                        print(f"  #{article.id} not answered, left for the next run")
                        continue
                    # No per-article line: BAML's own log already shows every
                    # verdict, and two copies of each buried the progress.
                    low = verdict.score < threshold_for(
                        str(publisher.trust), str(publisher.kind)
                    )
                    reason = sanitize_llm_text(verdict.reason)
                    rescored += 1
                    marked += int(low)
                    if write:
                        article.score = verdict.score
                        article.score_reason = reason
                        article.rescored_at = now
                        article.marked_for_deletion_at = now if low else None
                        session.add(article)
                if write:
                    session.commit()
                # One line per batch, flushed: piped through tee, stdout is
                # block-buffered and the line would otherwise show up late.
                print(
                    f"[{taken}/{total}] rescored {rescored}, marked {marked}, "
                    f"not answered {unanswered}",
                    flush=True,
                )
                wait_ms(SCORE_BATCH_PAUSE_MS)
        except KeyboardInterrupt:
            session.rollback()
            print(
                "\nInterrupted: the batch in flight was not written. Run again to resume."
            )
            return 130
        finally:
            print(
                f"\nRescored {rescored}, marked {marked} for deletion "
                f"(score < {SCORE_THRESHOLD}, < {CURATED_INDIVIDUAL_THRESHOLD} for "
                f"curated individuals), {unanswered} not answered."
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
