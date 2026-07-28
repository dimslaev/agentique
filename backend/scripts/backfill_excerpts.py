"""Recompute every article's excerpt from its stored content.

Two reasons to run this:

- After the migration. `summary` was renamed to `excerpt` and kept its text, so
  articles ingested before the change still carry an LLM summary rather than a
  slice of the article. This makes the column uniform.
- After changing `EXCERPT_CHARS` or the sanitizer, to apply it to the back
  catalogue instead of only to new articles.

    cd backend && uv run python -m scripts.backfill_excerpts [--limit N] [--dry-run]

No LLM, no network — pure text processing over rows already in the DB, so it is
cheap to re-run and safe to interrupt. Articles whose `content` is empty are
left alone rather than blanked: an old summary beats no card text at all.
"""

from __future__ import annotations

import argparse

from sqlmodel import Session, col, select

from app.core.db import engine
from app.models import Article
from pipeline.excerpt import to_excerpt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would change without writing it",
    )
    args = parser.parse_args()

    with Session(engine) as session:
        statement = select(Article).order_by(col(Article.id))
        if args.limit:
            statement = statement.limit(args.limit)
        articles = session.exec(statement).all()

        changed = 0
        skipped = 0
        for article in articles:
            if not (article.content or "").strip():
                skipped += 1
                continue
            fresh = to_excerpt(article.content)
            if not fresh or fresh == article.excerpt:
                continue
            changed += 1
            if args.dry_run:
                print(f"#{article.id}\n  was: {article.excerpt}\n  now: {fresh}\n")
            else:
                article.excerpt = fresh
                session.add(article)

        if not args.dry_run:
            session.commit()

        print(
            f"{changed} excerpt(s) rewritten, {skipped} skipped for want of content, "
            f"{len(articles) - changed - skipped} already current."
        )
        if args.dry_run:
            print("(dry run — nothing written)")


if __name__ == "__main__":
    main()
