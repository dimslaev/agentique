"""Give the existing corpus its categories.

The migration drops `tag`/`article_tag`, so every article already in the DB
lands categoryless: reachable by search and by publisher, but in no homepage
lane. This runs the same MatchCategories call the pipeline uses over those
articles and writes the join rows.

    cd backend && uv run python -m scripts.backfill_categories [--limit N] [--dry-run]

Two deliberate differences from the pipeline:

- It reads the stored `excerpt` when there is one, falling back to raw content.
  The excerpt is already sanitized, so it is a cleaner signal than the first few
  hundred characters of a markdown README.
- It does NOT delete articles that match nothing. The pipeline refuses to store
  them in the first place, but silently deleting published rows out from under
  the site is a different and much larger decision. They stay, uncategorised, and
  the counts printed at the end say how many there are — that number is the
  honest estimate of how much of the old corpus the new filter would not have
  admitted.

Resumable: articles that already have categories are skipped, so an interrupted
run can just be re-run.
"""

from __future__ import annotations

import argparse

from sqlmodel import Session, col, select

from app.core.db import engine
from app.models import Article, ArticleCategory, Publisher
from baml_client.sync_client import b
from baml_client.types import ArticleInput
from pipeline.categories import (
    load_vocabulary,
    validate_categories,
    write_article_categories,
)
from pipeline.steps.categorize import (
    MATCH_BATCH,
    MATCH_BATCH_PAUSE_MS,
    category_options,
)
from pipeline.utils import log, wait_ms

SNIPPET_CAP = 400


def uncategorized(
    session: Session, limit: int | None
) -> list[tuple[int, str, str, str]]:
    """(id, title, source name, snippet) for articles with no category yet."""
    statement = (
        select(
            Article.id, Article.title, Publisher.name, Article.excerpt, Article.content
        )
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .where(col(Article.id).not_in(select(ArticleCategory.article_id)))
        .order_by(col(Article.published_at).desc())
    )
    if limit:
        statement = statement.limit(limit)
    rows = session.exec(statement).all()
    return [
        (aid, title, source or "", ((excerpt or content or "").strip())[:SNIPPET_CAP])
        for aid, title, source, excerpt, content in rows
        if aid is not None
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be written without writing it",
    )
    args = parser.parse_args()

    with Session(engine) as session:
        vocab = load_vocabulary(session)
        rows = uncategorized(session, args.limit)
        if not rows:
            print("nothing to backfill")
            return

        print(f"{len(rows)} uncategorised articles, {len(vocab.slugs)} categories")
        options = category_options(vocab)
        by_id = {str(aid): aid for aid, _, _, _ in rows}

        matched = 0
        for i in range(0, len(rows), MATCH_BATCH):
            batch = rows[i : i + MATCH_BATCH]
            # The BAML call keys on url; the article id stands in for it here so
            # results map back to rows without a second lookup.
            inputs = [
                ArticleInput(
                    url=str(aid), title=title, source=source, snippet=snippet or None
                )
                for aid, title, source, snippet in batch
            ]
            try:
                results = b.MatchCategories(inputs, options)
            except Exception as e:
                log(f"  batch {i // MATCH_BATCH + 1} failed, skipping: {e}")
                continue

            for result in results:
                article_id = by_id.get(result.url)
                if article_id is None:
                    continue
                slugs = validate_categories(list(result.categories), vocab.slugs)
                if not slugs:
                    continue
                matched += 1
                print(f"  #{article_id}: {', '.join(slugs)}")
                if not args.dry_run:
                    write_article_categories(session, article_id, slugs, vocab)

            if not args.dry_run:
                session.commit()
            if i + MATCH_BATCH < len(rows):
                wait_ms(MATCH_BATCH_PAUSE_MS)

        unmatched = len(rows) - matched
        print(
            f"\n{matched}/{len(rows)} matched at least one category. "
            f"{unmatched} matched none — that is the share of the old corpus the "
            f"new filter would not have admitted."
        )
        if args.dry_run:
            print("(dry run — nothing written)")


if __name__ == "__main__":
    main()
