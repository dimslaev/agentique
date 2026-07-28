"""Step 5: what is left to do once an article is in the DB.

Two things: rewrite the title, and embed. Everything else the article carries —
categories, excerpt, format — was settled before insert, so a row is never
half-built. Each part is best-effort and commits its own work: a failure here
costs one field, never the article, and never the rest of the run.

This step used to also summarize, one LLM call per article. That is gone; the
card text is now a deterministic excerpt written at insert (pipeline/excerpt.py).
The title rewrite is the only LLM call left after insert.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models import Article
from baml_client.sync_client import b
from pipeline import keep_drop
from pipeline.embedding import embed_batch
from pipeline.llm_text import (
    is_valid_title,
    sanitize_llm_text,
    strip_title_wrappers,
)
from pipeline.steps import to_baml_input
from pipeline.types import FetchedArticle
from pipeline.utils import log, wait_ms

# Batch size for the title call. Kept small on purpose: a long list invites the
# model to blend one article's details into another's output, and a failed call
# costs the whole batch.
TITLE_BATCH = 10
BATCH_PAUSE_MS = 1000
# ─── Titles ──────────────────────────────────────────────────────────────────


def accept_title(raw: str | None, current: str, source: str) -> str | None:
    """The rewritten title to store, or None to keep the one we have. Pure.

    A rewrite is only an improvement if it survives every gate: it must clean up
    to something non-empty and different, look like a title, and not have leaked
    the source name into itself.
    """
    if not raw:
        return None
    sanitized = strip_title_wrappers(sanitize_llm_text(raw))
    if not sanitized or sanitized == current:
        return None
    if not is_valid_title(sanitized):
        log(f'  Skip rewrite (malformed): "{sanitized[:80]}"')
        return None
    if source.lower() in sanitized.lower():
        log(f'  Skip rewrite (source name leaked): "{sanitized}"')
        return None
    return sanitized


def improve_titles(session: Session, inserted: list[FetchedArticle]) -> None:
    if not inserted:
        return

    log(f"  Improving {len(inserted)} titles...")

    # ImproveTitles takes a list and echoes each input's url back on the
    # TitleFix, so results are matched by url rather than by position. Batched
    # rather than one call for everything: see the batch-size note above.
    fix_by_url: dict[str, str] = {}
    for i in range(0, len(inserted), TITLE_BATCH):
        batch = inserted[i : i + TITLE_BATCH]
        try:
            fixes = b.ImproveTitles([to_baml_input(item) for item in batch])
        except Exception as e:
            log(f"  Title improve failed for batch {i // TITLE_BATCH + 1}: {e}")
            continue
        fix_by_url.update({f.url: f.title for f in fixes})
        if i + TITLE_BATCH < len(inserted):
            wait_ms(BATCH_PAUSE_MS)

    changed = False
    for item in inserted:
        sanitized = accept_title(
            fix_by_url.get(item["url"]), item["title"], item["source"]
        )
        if not sanitized:
            continue
        article = session.get(Article, item["id"])
        if article:
            article.title = sanitized
            session.add(article)
            changed = True
        log(f'  Improved title #{item["id"]}: "{item["title"]}" -> "{sanitized}"')
        item["title"] = sanitized

    if changed:
        session.commit()


# ─── Embedding ───────────────────────────────────────────────────────────────


def embed_articles(session: Session, items: list[FetchedArticle]) -> None:
    if not items:
        return

    log(f"  Embedding {len(items)} articles...")

    # Built by keep_drop so the string is identical to the one its weights were
    # distilled against — the pre-filter and this step must embed the same text.
    # The second half used to be the LLM summary and is now the excerpt; both
    # are "summary-or-snippet" as far as the distilled weights are concerned.
    texts = [
        keep_drop.to_embedding_text(item["title"], item.get("excerpt"))
        for item in items
    ]
    try:
        vecs = embed_batch(texts)
    except Exception as e:
        log(f"  Embed batch failed, continuing: {e}")
        return

    for item, vec in zip(items, vecs, strict=True):
        article = session.get(Article, item["id"])
        if article:
            article.embedding = vec
            session.add(article)

    session.commit()
