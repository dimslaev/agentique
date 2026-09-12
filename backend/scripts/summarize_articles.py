"""Backfill `Article.summary` in the Julia Evans voice, via BAML SummarizeArticle.

Continues the review-batch rewrite (reports/article-review-*.csv already
covers those ids) across every other article. Rows inserted before the
pipeline's summarize step carry a summary from a retired pipeline function
baked into the prod dump (see .ignored/summary-rewrite.txt) or none at all, so
every remaining row gets rewritten or added the same way. Same call and
output checks as pipeline/steps/summarize.py.

Resumable: each article is committed and checkpointed right after its BAML
call, so a stopped run (Ctrl+C, dropped ssh, crash) loses at most the one
article in flight. Re-running picks up right after the last completed id.

    cd backend && uv run --env-file ../.env python -m scripts.summarize_articles
    cd backend && uv run --env-file ../.env python -m scripts.summarize_articles --limit 5 --write
    cd backend && uv run --env-file ../.env python -m scripts.summarize_articles --write --limit 500  # a batch of the full run

Uses the Nemotron client with no fallback (see baml_src/summarize.baml), so a
provider outage fails the row rather than quietly switching voice.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from sqlmodel import Session, col, func, select

from app.catalog.models import Article
from app.platform.db import engine
from app.platform.logging import wait_ms
from pipeline.steps.fetch import MIN_SUMMARIZABLE_CHARS
from pipeline.steps.summarize import (
    CALL_PAUSE_MS,
    MAX_CONTENT_CHARS,
    bullet_count,
    summarize,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
# Ids the manual QA review already rewrote (or deleted, so they're just gone) -
# skip them here rather than spend a second LLM call on the same article.
REVIEWED_CSV = REPO_ROOT / "reports" / "article-review-2026-07-11_2026-09-11.csv"
CHECKPOINT_FILE = REPO_ROOT / ".ignored" / "summarize-checkpoint.txt"


def reviewed_ids(csv_path: Path) -> set[int]:
    if not csv_path.exists():
        return set()
    with csv_path.open(newline="") as f:
        return {int(row["id"]) for row in csv.DictReader(f)}


def load_checkpoint(path: Path) -> int:
    if not path.exists():
        return 0
    return int(path.read_text().strip() or 0)


def save_checkpoint(path: Path, article_id: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(article_id))


def pick_articles(
    session: Session, after_id: int, skip_ids: set[int], limit: int
) -> list[Article]:
    stmt = select(Article).where(
        col(Article.id) > after_id,
        func.length(col(Article.content)) >= MIN_SUMMARIZABLE_CHARS,
    )
    if skip_ids:
        stmt = stmt.where(col(Article.id).notin_(skip_ids))
    stmt = stmt.order_by(col(Article.id).asc()).limit(limit)
    return list(session.exec(stmt))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=3, help="articles to process")
    parser.add_argument(
        "--write", action="store_true", help="persist the summary (default: print only)"
    )
    parser.add_argument("--checkpoint-file", type=Path, default=CHECKPOINT_FILE)
    parser.add_argument(
        "--reset-checkpoint",
        action="store_true",
        help="ignore/clear the checkpoint, start from id 0",
    )
    args = parser.parse_args()

    if args.reset_checkpoint and args.checkpoint_file.exists():
        args.checkpoint_file.unlink()

    skip_ids = reviewed_ids(REVIEWED_CSV)
    after_id = load_checkpoint(args.checkpoint_file)

    with Session(engine) as session:
        articles = pick_articles(session, after_id, skip_ids, args.limit)
        if not articles:
            print(f"No more articles to summarize after id {after_id}.")
            return

        written = 0
        for i, article in enumerate(articles):
            words = len((article.content or "")[:MAX_CONTENT_CHARS].split())
            bullets = bullet_count(words)
            summary = summarize(article.title, article.content or "")

            print(f"\n{'=' * 78}")
            print(f"#{article.id}  {article.title}")
            print(f"{article.url}")
            print(f"{words} words -> {bullets} bullets")
            print("-" * 78)
            print(summary or "(unusable summary - row left as is)")

            if args.write and summary:
                assert article.id is not None
                article.summary = summary
                session.add(article)
                session.commit()
                save_checkpoint(args.checkpoint_file, article.id)
                written += 1

            if i + 1 < len(articles):
                wait_ms(CALL_PAUSE_MS)

        if args.write:
            checkpoint = load_checkpoint(args.checkpoint_file)
            print(f"\nWrote {written} summaries. Checkpoint at #{checkpoint}.")


if __name__ == "__main__":
    main()
