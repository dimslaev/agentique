"""Step 2: drop what we have already seen or cannot reach.

Ordered cheapest-first: a DB lookup, then DNS — so nothing further downstream
ever sees a URL we already have or a domain that cannot resolve.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import dns.resolver
from sqlmodel import Session, select

from app.models import Article, ScoredUrl
from pipeline.types import FetchedArticle
from pipeline.utils import log

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
