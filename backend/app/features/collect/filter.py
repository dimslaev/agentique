"""Drop what we have already seen, before anything is spent on it.

A URL that is an Article, a pending candidate or a settled reject is never
fetched and judged again. A GitHub repo under `GITHUB_MIN_STARS` is rejected
before the agent sees it (the agent let a 13-star solo repo in on 2026-11-21).
Everything else, topic, reach and duplicates, the curation agent judges itself
(ADR 11).
"""

from __future__ import annotations

import os

from sqlmodel import Session, col, select

from app.core.db.article import Article
from app.core.db.ledger import Reject, RejectStage, record_reject
from app.core.db.publisher import Publisher, PublisherKind
from app.core.github import github_repo_from_url, repo_for
from app.core.logging import log
from app.features.collect.model import Candidate, RawItem

# Labs and companies ship new repos that are worth reading before they have stars.
STAR_EXEMPT_KINDS = {PublisherKind.lab, PublisherKind.company}


def filter_known_urls[T: RawItem](
    session: Session, articles: list[T], label: str
) -> list[T]:
    if not articles:
        return []
    # The same post arrives with and without a trailing slash, from different
    # sources (kernel.dev came back as a new candidate on 2026-11-20).
    all_urls = [u for a in articles for u in _slash_variants(a["url"])]

    existing_urls = set(
        session.exec(select(Article.url).where(col(Article.url).in_(all_urls))).all()
    )
    scored_urls = set(
        session.exec(select(Reject.url).where(col(Reject.url).in_(all_urls))).all()
    )

    known = existing_urls | scored_urls
    fresh = [
        a for a in articles if not any(u in known for u in _slash_variants(a["url"]))
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


def _slash_variants(url: str) -> tuple[str, str]:
    """``url`` with and without its trailing slash. Pure."""
    bare = url.rstrip("/")
    return bare, f"{bare}/"


def github_min_stars() -> int:
    """Stars a GitHub repo needs to reach the agent; 0 turns the gate off."""
    return int(os.environ.get("GITHUB_MIN_STARS", "50"))


def filter_thin_repos(
    session: Session, articles: list[Candidate], label: str
) -> list[Candidate]:
    """Reject GitHub repos under `github_min_stars()`, recorded as `thin_repo`.

    A failed lookup (rate limit, 404, timeout) keeps the candidate: unknown is
    never read as zero.
    """
    min_stars = github_min_stars()
    if not articles or min_stars <= 0:
        return articles

    kinds = dict(
        session.exec(
            select(Publisher.id, Publisher.kind).where(
                col(Publisher.id).in_({a["publisher_id"] for a in articles})
            )
        ).all()
    )
    kept: list[Candidate] = []
    dropped = 0
    for a in articles:
        repo = github_repo_from_url(a["url"])
        if repo is None or kinds.get(a["publisher_id"]) in STAR_EXEMPT_KINDS:
            kept.append(a)
            continue
        data = repo_for(*repo)
        stars = data.get("stargazers_count") if data else None
        if isinstance(stars, int) and stars < min_stars:
            log(f"  Dropped thin repo: {a['url']} ({stars} stars < {min_stars})")
            record_reject(session, a, RejectStage.thin_repo, detail={"stars": stars})
            dropped += 1
            continue
        kept.append(a)

    if dropped:
        session.commit()
        log(f"  Filtered {dropped} GitHub repos under {min_stars} stars from {label}")
    return kept
