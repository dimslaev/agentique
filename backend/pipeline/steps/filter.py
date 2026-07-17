"""Step 2: drop what we have already seen, cannot reach, or already carry.

Ordered cheapest-first: a DB lookup, then DNS, then an LLM dedup call — so the
expensive check only ever sees what the cheap ones could not rule out.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import dns.resolver
from sqlmodel import Session, select

from app.models_agentique import Article, Publisher, ScoredUrl
from baml_client.sync_client import b
from baml_client.types import ExistingArticle
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


def dedup_semantic(
    session: Session, articles: list[FetchedArticle], label: str
) -> list[FetchedArticle]:
    if not articles:
        return articles

    cutoff = datetime.now(UTC) - timedelta(days=DEDUP_WINDOW_DAYS)
    # Dedup only needs url/title/publisher-name — not content (KBs each) or the
    # embedding. Select just those columns and join the publisher name in one
    # query, rather than loading whole Article rows plus a second lookup.
    recent_rows = session.exec(
        select(Article.url, Article.title, Publisher.name)
        .join(Publisher, Publisher.id == Article.publisher_id, isouter=True)
        .where(Article.published_at >= cutoff)
    ).all()

    if not recent_rows:
        return articles

    log(f"  Deduplicating against {len(recent_rows)} recent DB articles...")

    new_inputs = [to_baml_input(a) for a in articles]
    existing_inputs = [
        ExistingArticle(url=str(url), title=title, source=name or "")
        for url, title, name in recent_rows
    ]

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
