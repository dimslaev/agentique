"""Orchestration: carry PipelineArticles from fetched to processed.

Each stage is a function that takes the session and a list of articles and
returns the survivors, so this module reads as the funnel it is:

    fetch -> filter_known -> dedup -> score -> persist -> enrich

Reliability rules that hold across every stage:
  * one article failing never sinks the rest — enrichment is per-item isolated;
  * the network is only re-touched for an article whose feed body was thin;
  * every LLM-authored field is sanitized/validated before it is stored;
  * a rejected URL is recorded so the next run does not re-fetch it.
"""

from __future__ import annotations

import numpy as np
from sqlmodel import Session

from app.models import Article, ArticleKind, ArticleTag
from pipeline_new import content, db, dedup, feeds, llm
from pipeline_new.embedding import drop_threshold, embed_batch, embed_text, get_model, keep_proba
from pipeline_new.types import PipelineArticle
from pipeline_new.util import hostname, log, parse_date, wait_ms

# ─── Tunables ────────────────────────────────────────────────────────────────

SCORE_THRESHOLD = 76  # 1-100; below this an article is not inserted
# Below this many chars a feed body is a teaser, and the summarizer fails on it
# ~30-40% of the time (vs ~2% above) — the one trigger for a network re-fetch.
MIN_CONTENT_CHARS = 500
PROMPT_CONTENT_CAP = 1500  # chars of body sent to the summarizer

SCORE_BATCH = 5
TAG_BATCH = 10
BATCH_PAUSE_MS = 1000  # stay under the provider rate limit between batches
DEDUP_WINDOW_DAYS = 14


# ─── Deterministic kind ──────────────────────────────────────────────────────


def kind_from_url(url: str) -> ArticleKind | None:
    """ArticleKind fixed by the URL host, or None when the host says nothing.
    The host is authoritative when conclusive, so we never ask the LLM for it."""
    host = hostname(url)
    if host in ("github.com", "gitlab.com"):
        return ArticleKind.repo
    if host in ("huggingface.co", "hf.co"):
        return ArticleKind.model
    if host in ("arxiv.org", "ar5iv.labs.arxiv.org"):
        return ArticleKind.paper
    return None


# ─── Stage: drop known URLs ──────────────────────────────────────────────────


def filter_known(session: Session, articles: list[PipelineArticle]) -> list[PipelineArticle]:
    if not articles:
        return []
    known = db.known_urls(session, [a.url for a in articles])
    fresh = [a for a in articles if a.url not in known]
    if known:
        log(f"  Dropped {len(articles) - len(fresh)} known/already-scored URLs")
    log(f"  {len(fresh)} new articles to process")
    return fresh


# ─── Stage: semantic dedup ───────────────────────────────────────────────────


def dedup_semantic(session: Session, articles: list[PipelineArticle]) -> list[PipelineArticle]:
    if not articles:
        return []
    recent = db.recent_articles(session, DEDUP_WINDOW_DAYS)
    if not recent:
        return articles

    existing = dedup.shortlist(articles, recent)
    if not existing:
        log(f"  No dedup shortlist among {len(recent)} recent articles; all unique")
        return articles

    log(f"  Shortlisted {len(existing)}/{len(recent)} recent articles for dedup check")
    dup_urls = llm.semantic_dedup(articles, existing)
    unique = [a for a in articles if a.url not in dup_urls]
    if dup_urls:
        log(f"  Dropped {len(dup_urls)} duplicates")
    return unique


# ─── Stage: pre-filter + score ───────────────────────────────────────────────


def _prefilter(session: Session, articles: list[PipelineArticle]) -> list[PipelineArticle]:
    """Drop obvious junk with the cheap classifier before the LLM scorer."""
    threshold = drop_threshold()
    if not articles or threshold <= 0:
        return articles

    vecs = get_model().encode([embed_text(a.title, a.content) for a in articles])
    survivors: list[PipelineArticle] = []
    dropped: list[str] = []
    for a, vec in zip(articles, vecs, strict=True):
        if keep_proba(np.asarray(vec)) < threshold:
            dropped.append(a.url)
        else:
            survivors.append(a)
    db.record_rejected(session, dropped)
    if dropped:
        log(f"  Pre-filter dropped {len(dropped)} as obvious junk; {len(survivors)} to scorer")
    return survivors


def score(session: Session, articles: list[PipelineArticle]) -> list[PipelineArticle]:
    articles = _prefilter(session, articles)
    if not articles:
        return []

    log(f"  Scoring {len(articles)} articles...")
    score_by_url: dict[str, int] = {}
    for i in range(0, len(articles), SCORE_BATCH):
        batch = articles[i : i + SCORE_BATCH]
        try:
            score_by_url.update(llm.score_batch(batch))
        except Exception as e:
            log(f"  Score batch {i // SCORE_BATCH + 1} failed, skipping: {e}")
        if i + SCORE_BATCH < len(articles):
            wait_ms(BATCH_PAUSE_MS)

    # A URL the scorer did not return scores 0 — a missing score is a reject.
    for a in articles:
        a.score = score_by_url.get(a.url, 0)
    articles.sort(key=lambda a: a.score, reverse=True)

    kept = [a for a in articles if a.score >= SCORE_THRESHOLD]
    below = [a for a in articles if a.score < SCORE_THRESHOLD]
    # Record only rejects: a keeper recorded here then lost to a crash before
    # insert would be dropped forever. Once inserted, the Article row makes it
    # known instead.
    db.record_rejected(session, [a.url for a in below])
    log(f"  {len(kept)}/{len(articles)} pass scoring (threshold {SCORE_THRESHOLD})")
    return kept


# ─── Stage: persist ──────────────────────────────────────────────────────────


def persist(session: Session, articles: list[PipelineArticle]) -> list[PipelineArticle]:
    inserted: list[PipelineArticle] = []
    for a in articles:
        row = Article(
            title=a.title,
            publisher_id=a.publisher_id,
            url=a.url,
            published_at=parse_date(a.published_date),
            score=a.score,
            content=a.content or "",
        )
        session.add(row)
        session.flush()
        assert row.id is not None
        a.id = row.id
        inserted.append(a)
        log(f"  Inserted #{row.id}: [{a.score}/100] {a.title}")
    session.commit()
    return inserted


# ─── Stage: enrich ───────────────────────────────────────────────────────────


def _refetch_thin(session: Session, articles: list[PipelineArticle]) -> None:
    """Fill in full content for articles whose feed body was a teaser. This is
    the only stage that re-touches the network, and only for what needs it."""
    thin = [a for a in articles if len(a.content) < MIN_CONTENT_CHARS]
    skipped = len(articles) - len(thin)
    if skipped:
        log(f"  {skipped}/{len(articles)} already have full content")
    if not thin:
        return

    recovered = content.fetch_readable_many([a.url for a in thin])
    for a in thin:
        full = recovered.get(a.url)
        if full:
            a.content = full
            row = session.get(Article, a.id)
            if row:
                row.content = full
                session.add(row)
    session.commit()


def _summarize(session: Session, articles: list[PipelineArticle]) -> None:
    """Summary + categories + kind per article, isolated so one failure costs
    one article. Full content -> summarize; thin/empty -> categorize by title.
    The URL host wins on kind whenever it is conclusive."""
    log(f"  Summarizing and categorizing {len(articles)} articles...")
    for a in articles:
        a.kind = kind_from_url(a.url)
        try:
            if a.content:
                a.summary, a.categories, llm_kind = llm.summarize(a, PROMPT_CONTENT_CAP)
                a.kind = a.kind or llm_kind
            else:
                a.categories = llm.categorize_title(a)
        except Exception as e:
            log(f"  Summarize failed for #{a.id}: {e}")

        row = session.get(Article, a.id)
        if row:
            row.summary = a.summary
            row.categories = a.categories
            if a.kind:
                row.kind = a.kind
            session.add(row)
    session.commit()


def _assign_tags(session: Session, articles: list[PipelineArticle]) -> None:
    vocab = db.load_tag_vocabulary(session)
    ids_by_slug = db.tag_ids_by_slug(session)
    log(f"  Assigning tags to {len(articles)} articles ({len(vocab)} in vocab)...")

    for i in range(0, len(articles), TAG_BATCH):
        batch = articles[i : i + TAG_BATCH]
        try:
            tags_by_id = llm.assign_tags_batch(batch, vocab)
        except Exception as e:
            log(f"  Tag batch {i // TAG_BATCH + 1} failed, skipping: {e}")
            tags_by_id = {}
        for a in batch:
            if a.id is None:
                continue
            slugs = (tags_by_id.get(a.id) or [])[:3]
            a.tags = slugs
            for slug in slugs:
                tag_id = ids_by_slug.get(slug)
                if tag_id is not None:
                    session.merge(ArticleTag(article_id=a.id, tag_id=tag_id))
            if slugs:
                log(f"    Tagged #{a.id}: {', '.join(slugs)}")
        if i + TAG_BATCH < len(articles):
            wait_ms(BATCH_PAUSE_MS)
    session.commit()


def _embed(session: Session, articles: list[PipelineArticle]) -> None:
    # Same text recipe as the pre-filter classifier, over title + summary.
    try:
        vecs = embed_batch([embed_text(a.title, a.summary) for a in articles])
    except Exception as e:
        log(f"  Embed failed, skipping: {e}")
        return
    for a, vec in zip(articles, vecs, strict=True):
        row = session.get(Article, a.id)
        if row:
            row.embedding = vec
            session.add(row)
    session.commit()


def enrich(session: Session, articles: list[PipelineArticle]) -> list[PipelineArticle]:
    if not articles:
        return []
    _refetch_thin(session, articles)
    _summarize(session, articles)
    _assign_tags(session, articles)
    _embed(session, articles)
    log("  Enrichment done")
    return articles


# ─── Run ─────────────────────────────────────────────────────────────────────


def run(session: Session) -> list[PipelineArticle]:
    """One full pass over every active RSS/substack feed. Returns the processed
    articles. Any per-stage exception aborts this run cleanly (rolled back by the
    caller); within enrichment, failures are already isolated per article."""
    log("=== RSS pipeline start ===")
    publishers = db.load_feed_publishers(session)

    fetched = feeds.fetch_all(publishers)
    fresh = filter_known(session, fetched)
    unique = dedup_semantic(session, fresh)
    kept = score(session, unique)
    inserted = persist(session, kept)
    processed = enrich(session, inserted)

    log(f"=== RSS pipeline complete: {len(processed)} articles processed ===")
    return processed
