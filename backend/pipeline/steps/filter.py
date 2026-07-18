"""Step 2: drop what we have already seen, cannot reach, or already carry.

Ordered cheapest-first: a DB lookup, then DNS, then an LLM dedup call — so the
expensive check only ever sees what the cheap ones could not rule out.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import dns.resolver
import numpy as np
from sqlmodel import Session, select

from app.models import Article, Publisher, ScoredUrl
from baml_client.sync_client import b
from baml_client.types import ExistingArticle
from pipeline import keep_drop
from pipeline.config import dedup_dist_threshold, dedup_topk
from pipeline.embedding import embed_batch
from pipeline.steps import to_baml_input
from pipeline.types import FetchedArticle
from pipeline.utils import log

DEDUP_WINDOW_DAYS = 14
DNS_CONCURRENCY = 10


def filter_known_urls(
    session: Session, articles: list[FetchedArticle], label: str
) -> list[FetchedArticle]:
    if not articles:
        return []
    all_urls = [a["url"] for a in articles]

    existing_urls = set(
        session.exec(select(Article.url).where(Article.url.in_(all_urls))).all()
    )
    scored_urls = set(
        session.exec(select(ScoredUrl.url).where(ScoredUrl.url.in_(all_urls))).all()
    )

    fresh = [
        a
        for a in articles
        if a["url"] not in existing_urls and a["url"] not in scored_urls
    ]

    if existing_urls or scored_urls:
        log(
            f"  Filtered {len(existing_urls)} known + {len(scored_urls)} already-scored URLs"
        )
    if not fresh:
        log(f"  No new articles from {label}")
        return []
    log(f"  {len(fresh)} new articles to process")
    return fresh


def _is_resolvable(url: str) -> bool:
    # Deliberately not pipeline.utils.hostname: that strips a "www." prefix, and
    # www.foo.com resolving says nothing about whether foo.com does. Resolve the
    # host exactly as the URL spells it.
    try:
        host = urlparse(url).hostname
        if not host:
            return False
        dns.resolver.resolve(host, "A")
        return True
    except dns.resolver.NXDOMAIN:
        return False
    except Exception:
        return True  # Other errors (timeout, etc.) - assume alive


def filter_dead_domains(
    articles: list[FetchedArticle], label: str
) -> list[FetchedArticle]:
    if not articles:
        return articles

    # DNS lookups are I/O-bound and each NXDOMAIN retry chain can take seconds;
    # run them in parallel like the source fetchers do.
    with ThreadPoolExecutor(max_workers=DNS_CONCURRENCY) as executor:
        oks = list(executor.map(lambda a: _is_resolvable(a["url"]), articles))

    alive = [a for a, ok in zip(articles, oks, strict=True) if ok]
    dead = [a for a, ok in zip(articles, oks, strict=True) if not ok]
    for a in dead:
        log(f"  Dropped dead URL: {a['url']}")
    if dead:
        log(f"  Filtered {len(dead)} dead-domain URLs from {label}")
    return alive


def _cosine_dist_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return 1 - (a_norm @ b_norm.T)


def _select_candidate_indices(
    new_vecs: np.ndarray, recent_vecs: np.ndarray, threshold: float, topk: int
) -> set[int]:
    """For each new-article vector, the recent-vector indices within
    ``threshold`` cosine distance, capped to the ``topk`` closest. Pure numpy:
    the pinned core of the shortlist, kept separate from embedding I/O so it
    can be tested with synthetic vectors."""
    dist = _cosine_dist_matrix(new_vecs, recent_vecs)

    candidate_idx: set[int] = set()
    for row in dist:
        within = np.where(row <= threshold)[0]
        if within.size == 0:
            continue
        if within.size > topk:
            within = within[np.argsort(row[within])[:topk]]
        candidate_idx.update(within.tolist())
    return candidate_idx


def _shortlist_candidates(
    articles: list[FetchedArticle],
    recent_rows: list[tuple[str, str, str | None, list[float] | None]],
) -> list[ExistingArticle]:
    """Cosine-distance shortlist of recent articles worth sending to the LLM
    dedup check, so the prompt scales with likely dupes instead of the whole
    window. Recent rows without a stored embedding cannot be shortlisted and
    are skipped (the 14-day window is expected to be fully embedded)."""
    # r[3] is Article.embedding — pgvector returns a numpy array on read, and
    # bool(array) raises for length > 1, so this must be an is-not-None check.
    embedded = [r for r in recent_rows if r[3] is not None]
    if not embedded:
        return []

    new_texts = [
        keep_drop.to_embedding_text(a["title"], a.get("content")) for a in articles
    ]
    new_vecs = np.array(embed_batch(new_texts), dtype=np.float32)
    recent_vecs = np.array([r[3] for r in embedded], dtype=np.float32)

    candidate_idx = _select_candidate_indices(
        new_vecs, recent_vecs, dedup_dist_threshold(), dedup_topk()
    )

    return [
        ExistingArticle(
            url=str(embedded[i][0]),
            title=embedded[i][1],
            source=embedded[i][2] or "",
        )
        for i in sorted(candidate_idx)
    ]


def dedup_semantic(
    session: Session, articles: list[FetchedArticle], label: str
) -> list[FetchedArticle]:
    if not articles:
        return articles

    cutoff = datetime.now(UTC) - timedelta(days=DEDUP_WINDOW_DAYS)
    recent_rows = session.exec(
        select(Article.url, Article.title, Publisher.name, Article.embedding)
        .join(Publisher, Publisher.id == Article.publisher_id, isouter=True)
        .where(Article.published_at >= cutoff)
    ).all()

    if not recent_rows:
        return articles

    existing_inputs = _shortlist_candidates(articles, recent_rows)
    if not existing_inputs:
        log(
            f"  No dedup shortlist matches among {len(recent_rows)} recent DB "
            f"articles; skipping LLM check, all {len(articles)} unique"
        )
        return articles

    log(
        f"  Shortlisted {len(existing_inputs)}/{len(recent_rows)} recent DB "
        f"articles for dedup LLM check"
    )

    new_inputs = [to_baml_input(a) for a in articles]

    try:
        matches = b.SemanticDedup(new_inputs, existing_inputs)
        merged_urls = {m.url for m in matches}
        for m in matches:
            log(f"  Dropped duplicate: {m.url} (matches existing: {m.existingUrl})")
        if merged_urls:
            log(f"  {len(merged_urls)} articles dropped as duplicates")
        unique = [a for a in articles if a["url"] not in merged_urls]
        if not unique:
            log(f"  No new unique articles from {label}")
        return unique
    except Exception as e:
        log(f"  Dedup failed, continuing without: {e}")
        return articles
