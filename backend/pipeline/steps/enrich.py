"""Step 5: everything we do to an article after it is in the DB.

Titles, summary + kind, embedding. What the article is *about* was already
settled before insert — categories are the admission rule, not an enrichment —
so this step only writes the card. Content is already full by now (the fetch
step fills it and drops anything it cannot), so summarize works from the real
article, not a teaser. Each part is best-effort and commits its own work: a
failure here costs one field, never the article, and never the rest of the run.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models import Article, ArticleKind
from baml_client.sync_client import b
from pipeline import keep_drop
from pipeline.embedding import embed_batch
from pipeline.heuristics import (
    PROMPT_CONTENT_CAP,
    github_repo_from_content,
    kind_from_url,
)
from pipeline.llm_text import (
    is_valid_summary,
    is_valid_title,
    sanitize_llm_text,
    strip_title_wrappers,
)
from pipeline.steps import to_baml_input
from pipeline.types import FetchedArticle, ProcessedArticle
from pipeline.utils import enum_value, log, wait_ms

# Batch size for the title call. Kept small on purpose: a long list invites the
# model to blend one article's details into another's output, and a failed call
# costs the whole batch.
TITLE_BATCH = 10
BATCH_PAUSE_MS = 1000
# Pause between the per-article summarize calls. These run one article at a time
# (not batched) so a slow or failed call costs a single article, never a whole
# batch — the delay keeps us under the provider's rate limit.
CALL_PAUSE_MS = 1000


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


# ─── Summary and kind ────────────────────────────────────────────────────────


def _to_kind(baml_kind) -> ArticleKind | None:
    """Map a BAML ArticleKind enum value -> models ArticleKind enum."""
    value = enum_value(baml_kind)
    try:
        return ArticleKind(value.lower())
    except ValueError:
        log(f"  Dropped unknown kind {value!r}")
        return None


def summarize(session: Session, items: list[FetchedArticle]) -> list[ProcessedArticle]:
    """Write each article's summary and kind from its content.

    Content is always full by the time an article gets here (the fetch step
    fills it and drops anything it cannot), so one ``Summarize`` call per
    article produces the summary and kind together. One LLM call per article
    with a delay between them: no batching, so a slow or failed call costs a
    single article. An article that somehow still has no content is skipped and
    logged rather than summarized from a bare title.

    The article's categories were decided before insert and are not revisited
    here — this only writes the card.
    """
    if not items:
        return []

    log(f"  Summarizing {len(items)} articles...")
    processed: list[ProcessedArticle] = []

    for idx, item in enumerate(items):
        art_id = item["id"]
        content = item.get("content") or ""
        if not content.strip():
            log(f"  Skip summary #{art_id}: no content")
            continue

        summary_text = ""
        # The URL host is authoritative when it is conclusive (a github.com link
        # is a repo); only ask the LLM when it is not.
        kind: ArticleKind | None = kind_from_url(item["url"])

        try:
            result = b.Summarize(item["title"], content[:PROMPT_CONTENT_CAP])
            summary_text = sanitize_llm_text(result.summary or "")
            if summary_text and not is_valid_summary(summary_text):
                log(f'  Drop summary #{art_id} (malformed): "{summary_text[:80]}"')
                summary_text = ""
            if not kind:
                kind = _to_kind(result.kind)
            if kind == ArticleKind.blog and github_repo_from_content(content):
                kind = ArticleKind.repo
        except Exception as e:
            log(f"  Summarize failed for #{art_id}: {e}")

        article = session.get(Article, art_id)
        if article:
            article.summary = summary_text
            if kind:
                article.kind = kind
            session.add(article)

        processed.append(
            {
                "id": art_id,
                "url": item["url"],
                "title": item["title"],
                "summary": summary_text,
                "categories": item["categories"],
            }
        )
        if idx + 1 < len(items):
            wait_ms(CALL_PAUSE_MS)

    session.commit()
    log("  Done summarizing")
    return processed


# ─── Embedding ───────────────────────────────────────────────────────────────


def embed_articles(session: Session, items: list[ProcessedArticle]) -> None:
    if not items:
        return

    log(f"  Embedding {len(items)} articles...")

    # Built by keep_drop so the string is identical to the one its weights were
    # distilled against — the pre-filter and this step must embed the same text.
    texts = [
        keep_drop.to_embedding_text(item["title"], item.get("summary"))
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
