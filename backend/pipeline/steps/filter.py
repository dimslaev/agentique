"""Step 2: drop what we have already seen, cannot reach, or already carry.

Ordered cheapest-first: a DB lookup, then DNS, then an embedding comparison —
so the expensive check only ever sees what the cheap ones could not rule out.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import dns.resolver
import numpy as np
from sqlmodel import Session, select

from app.models import Article, Publisher, ScoredUrl
from app.platform.logging import log
from pipeline import keep_drop
from pipeline.config import dedup_dist_threshold, github_min_stars
from pipeline.embedding import embed_batch
from pipeline.heuristics import KNOWN_REPO_OWNERS, github_repo_from_url
from pipeline.sources.github_stars import stars_for
from pipeline.steps import SNIPPET_CAP
from pipeline.types import FetchedArticle

DNS_CONCURRENCY = 10
# How far back to look for an article we already carry. Same-story reposts
# cluster within days of each other; beyond this a genuine new article about an
# old topic is not a duplicate, and the comparison set stops growing forever.
DEDUP_WINDOW_DAYS = 14


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
    # Deliberately not pipeline.urls.hostname: that strips a "www." prefix, and
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


def filter_thin_repos(
    session: Session, articles: list[FetchedArticle], label: str
) -> list[FetchedArticle]:
    """Drop links to GitHub repos nobody uses.

    An aggregator cannot tell a project from an upload: a repo with two stars,
    posted by its author the day they created it, arrives with the same shape as
    a runtime half the field depends on, and a scorer reading title and README
    reliably rates it as if the pitch were the product. Stars are the outside
    view, and one API call answers it.

    Only repo URLs cost a lookup. Repos under ``KNOWN_REPO_OWNERS`` skip it —
    a PR against llama.cpp is worth reading on its own merits, and it would pass
    anyway. A lookup that fails or is rate-limited returns None and the article
    is kept: the gate never deletes an article because GitHub was unreachable.

    Drops are recorded in ``ScoredUrl``. Unlike the recency-based holds in the
    Hacker News source, this verdict does not change inside a 48h window, so
    re-fetching and re-checking the same repo tomorrow would just spend the
    request budget again.
    """
    min_stars = github_min_stars()
    if not articles or min_stars <= 0:
        return articles

    repo_by_index: dict[int, tuple[str, str]] = {}
    for i, a in enumerate(articles):
        repo = github_repo_from_url(a["url"])
        if repo and repo[0].lower() not in KNOWN_REPO_OWNERS:
            repo_by_index[i] = repo
    if not repo_by_index:
        return articles

    stars = stars_for(list(repo_by_index.values()))

    kept: list[FetchedArticle] = []
    dropped = 0
    for i, a in enumerate(articles):
        repo = repo_by_index.get(i)
        count = stars.get(repo) if repo else None
        if repo and count is not None and count < min_stars:
            log(f"  Dropped thin repo: {a['url']} ({count} stars < {min_stars})")
            session.merge(ScoredUrl(url=a["url"]))
            dropped += 1
            continue
        kept.append(a)

    if dropped:
        session.commit()
        log(
            f"  Filtered {dropped}/{len(repo_by_index)} GitHub repos under "
            f"{min_stars} stars from {label}"
        )
    return kept


def _cosine_dist_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return 1 - (a_norm @ b_norm.T)


def _nearest_within(
    new_vecs: np.ndarray, existing_vecs: np.ndarray, threshold: float
) -> dict[int, int]:
    """Map each new-article index to the closest existing index within
    ``threshold`` cosine distance, or omit it when nothing is close enough.

    Pure numpy, kept separate from embedding I/O so it can be tested on
    synthetic vectors with no model load.
    """
    if new_vecs.size == 0 or existing_vecs.size == 0:
        return {}

    dist = _cosine_dist_matrix(new_vecs, existing_vecs)
    matches: dict[int, int] = {}
    for i, row in enumerate(dist):
        j = int(np.argmin(row))
        if row[j] <= threshold:
            matches[i] = j
    return matches


def dedup_semantic(
    session: Session, articles: list[FetchedArticle], label: str
) -> list[FetchedArticle]:
    """Drop articles we already carry, judged by embedding distance alone.

    Runs before scoring so a duplicate never costs an LLM call. Compares each
    candidate against every article ingested in the last DEDUP_WINDOW_DAYS, and
    against the ones already kept from this same batch — two feeds carrying one
    story in a single run would otherwise both survive.
    """
    threshold = dedup_dist_threshold()
    if not articles or threshold <= 0:
        return articles

    cutoff = datetime.now(UTC) - timedelta(days=DEDUP_WINDOW_DAYS)
    # created_at, not published_at: published_at is nullable and a story we
    # ingested yesterday is one we carry now, whatever date it claims.
    recent_rows = session.exec(
        select(Article.url, Article.title, Publisher.name, Article.embedding)
        .join(Publisher, Publisher.id == Article.publisher_id, isouter=True)
        .where(Article.created_at >= cutoff, Article.embedding.is_not(None))
    ).all()

    # Must match how the stored embedding was built (enrich.embed_articles
    # embeds content capped at SNIPPET_CAP), or an article fails to match its
    # own row in the DB and the comparison is meaningless.
    new_texts = [
        keep_drop.to_embedding_text(a["title"], (a.get("content") or "")[:SNIPPET_CAP])
        for a in articles
    ]
    new_vecs = np.array(embed_batch(new_texts), dtype=np.float32)

    # r[3] is Article.embedding — pgvector returns a numpy array on read, and
    # bool(array) raises for length > 1, so this must be an is-not-None check.
    embedded = [r for r in recent_rows if r[3] is not None]
    recent_vecs = (
        np.array([r[3] for r in embedded], dtype=np.float32)
        if embedded
        else np.empty((0, new_vecs.shape[1]), dtype=np.float32)
    )

    against_db = _nearest_within(new_vecs, recent_vecs, threshold)

    unique: list[FetchedArticle] = []
    kept_vecs: list[np.ndarray] = []
    for i, a in enumerate(articles):
        j = against_db.get(i)
        if j is not None:
            log(f"  Dropped duplicate: {a['url']} (already carry: {embedded[j][0]})")
            continue

        if kept_vecs:
            intra = _nearest_within(
                new_vecs[i : i + 1], np.array(kept_vecs, dtype=np.float32), threshold
            )
            if 0 in intra:
                log(
                    f"  Dropped duplicate: {a['url']} "
                    f"(same batch: {unique[intra[0]]['url']})"
                )
                continue

        unique.append(a)
        kept_vecs.append(new_vecs[i])

    dropped = len(articles) - len(unique)
    if dropped:
        log(
            f"  Deduped {dropped}/{len(articles)} against "
            f"{len(embedded)} articles from the last {DEDUP_WINDOW_DAYS} days"
        )
    if not unique:
        log(f"  No new unique articles from {label}")
    return unique
