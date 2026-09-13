"""Step 2: drop what we have already seen, cannot reach, or already carry.

Ordered cheapest-first: a DB lookup, then DNS, then an embedding comparison —
so the expensive check only ever sees what the cheap ones could not rule out.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import dns.resolver
import numpy as np
from sqlmodel import Session, select

from app.catalog.models import Article, Publisher
from app.platform.logging import log
from pipeline import keep_drop
from pipeline.embedding import embed_batch
from pipeline.github import github_repo_from_url, is_known_owner
from pipeline.models import Reject, RejectStage
from pipeline.rejects import record_reject
from pipeline.sources.github_stars import stars_for
from pipeline.steps import SNIPPET_CAP
from pipeline.types import Candidate

DNS_CONCURRENCY = 10
# How far back to look for an article we already carry. Same-story reposts
# cluster within days of each other; beyond this a genuine new article about an
# old topic is not a duplicate, and the comparison set stops growing forever.
DEDUP_WINDOW_DAYS = 14


def github_min_stars() -> int:
    """Stars a GitHub repo needs before we treat it as something builders use.
    0 disables the repo gate.

    Aimed at the "solo repo with two stars, posted by its author" case, not at
    ranking projects: a real tool that reaches an aggregator is well past this
    by the time it does. Repos under an owner ``github.is_known_owner`` recognises
    skip the check entirely.
    """
    return int(os.environ.get("GITHUB_MIN_STARS", "50"))


def dedup_dist_threshold() -> float:
    """Cosine-distance cutoff below which two articles are the same story;
    0 disables dedup entirely.

    Same-story pairs empirically sit at 0.29-0.35. The old shortlist used 0.45
    to favour recall because an LLM still made the final call - that call is
    gone, so this now drops on its own and sits at the bottom of the band
    instead. Erring tight costs a duplicate slipping through; erring loose
    silently deletes a real article, which is the worse failure.
    """
    return float(os.environ.get("DEDUP_DIST_THRESHOLD", "0.30"))


def filter_known_urls(
    session: Session, articles: list[Candidate], label: str
) -> list[Candidate]:
    if not articles:
        return []
    all_urls = [a["url"] for a in articles]

    existing_urls = set(
        session.exec(select(Article.url).where(Article.url.in_(all_urls))).all()
    )
    scored_urls = set(
        session.exec(select(Reject.url).where(Reject.url.in_(all_urls))).all()
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


def filter_dead_domains(articles: list[Candidate], label: str) -> list[Candidate]:
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
    session: Session, articles: list[Candidate], label: str
) -> list[Candidate]:
    """Drop links to GitHub repos nobody uses.

    An aggregator cannot tell a project from an upload: a repo with two stars,
    posted by its author the day they created it, arrives with the same shape as
    a runtime half the field depends on, and a scorer reading title and README
    reliably rates it as if the pitch were the product. Stars are the outside
    view, and one API call answers it.

    Only repo URLs cost a lookup. Repos under a known owner skip it —
    a PR against llama.cpp is worth reading on its own merits, and it would pass
    anyway. A lookup that fails or is rate-limited returns None and the article
    is kept: the gate never deletes an article because GitHub was unreachable.

    Drops are recorded as rejects. Unlike the recency-based holds in the
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
        if repo and not is_known_owner(repo[0]):
            repo_by_index[i] = repo
    if not repo_by_index:
        return articles

    stars = stars_for(list(repo_by_index.values()))

    kept: list[Candidate] = []
    dropped = 0
    for i, a in enumerate(articles):
        repo = repo_by_index.get(i)
        count = stars.get(repo) if repo else None
        if repo and count is not None and count < min_stars:
            log(f"  Dropped thin repo: {a['url']} ({count} stars < {min_stars})")
            record_reject(session, a, RejectStage.thin_repo, detail={"stars": count})
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
    session: Session, articles: list[Candidate], label: str
) -> list[Candidate]:
    """Drop articles we already carry, judged by embedding distance alone.

    Runs before scoring so a duplicate never costs an LLM call. Compares each
    candidate against every article ingested in the last DEDUP_WINDOW_DAYS, and
    against the ones already kept from this same batch — two feeds carrying one
    story in a single run would otherwise both survive.

    Duplicates are recorded as rejects with the URL they duplicate: that stops
    re-embedding them every run, and counts how many outlets carried a story.
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
        keep_drop.to_embedding_text(a["title"], a["content"][:SNIPPET_CAP])
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

    unique: list[Candidate] = []
    kept_vecs: list[np.ndarray] = []
    for i, a in enumerate(articles):
        j = against_db.get(i)
        if j is not None:
            dup_of = embedded[j][0]
            log(f"  Dropped duplicate: {a['url']} (already carry: {dup_of})")
            record_reject(session, a, RejectStage.duplicate, detail={"dup_of": dup_of})
            continue

        if kept_vecs:
            intra = _nearest_within(
                new_vecs[i : i + 1], np.array(kept_vecs, dtype=np.float32), threshold
            )
            if 0 in intra:
                dup_of = unique[intra[0]]["url"]
                log(f"  Dropped duplicate: {a['url']} (same batch: {dup_of})")
                record_reject(
                    session, a, RejectStage.duplicate, detail={"dup_of": dup_of}
                )
                continue

        unique.append(a)
        kept_vecs.append(new_vecs[i])

    dropped = len(articles) - len(unique)
    if dropped:
        session.commit()
        log(
            f"  Deduped {dropped}/{len(articles)} against "
            f"{len(embedded)} articles from the last {DEDUP_WINDOW_DAYS} days"
        )
    if not unique:
        log(f"  No new unique articles from {label}")
    return unique
