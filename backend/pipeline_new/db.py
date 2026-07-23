"""Database engine + the reads/writes the pipeline needs.

The engine is built lazily so importing a module to test a pure function needs
no database. Query helpers live here so the stage modules stay about logic, not
SQL, and the DB shape is described in one place.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine
from sqlmodel import Session, create_engine, select

from app.models import (
    Article,
    LinkPlatform,
    Publisher,
    PublisherType,
    ScoredUrl,
    Tag,
)
from pipeline_new.config import postgres_url
from pipeline_new.types import FeedPublisher
from pipeline_new.util import log

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(postgres_url())
    return _engine


# ─── Publishers ──────────────────────────────────────────────────────────────


def load_feed_publishers(session: Session) -> list[FeedPublisher]:
    """Active RSS/substack publishers with an ``rss`` link, ready to poll.

    Substack links are normalized to their ``/feed`` rss URL at the DB level, so
    both kinds expose a single ``rss`` link to read here. Iterating known
    publishers (rather than resolving fetched items back to a publisher by name)
    means every article's provenance is known before the network is touched —
    there is no unknown-source quarantine path to reason about.
    """
    rows = session.exec(
        select(Publisher).where(
            Publisher.is_active == True,  # noqa: E712
            Publisher.type.in_([PublisherType.rss, PublisherType.substack]),
        )
    ).all()

    publishers: list[FeedPublisher] = []
    for pub in rows:
        # Link keys survive the JSON round-trip as either enums or plain strings;
        # normalize to plain strings once so the lookup is unambiguous.
        links = {str(getattr(k, "value", k)): v for k, v in (pub.links or {}).items()}
        rss = links.get(LinkPlatform.rss.value)
        if pub.id is not None and rss:
            publishers.append(
                FeedPublisher(id=pub.id, name=pub.name, rss_url=rss, trust=pub.trust)
            )

    log(f"Loaded {len(publishers)} active RSS/substack publishers")
    return publishers


# ─── Tag vocabulary ──────────────────────────────────────────────────────────


def load_tag_vocabulary(session: Session) -> dict[str, str]:
    """The controlled tag vocabulary as ``{slug: when-to-apply description}``.

    Raises if empty — an unseeded vocabulary would silently tag nothing, which
    is worse than failing loudly.
    """
    rows = session.exec(select(Tag)).all()
    if not rows:
        raise RuntimeError(
            "tag table is empty — the controlled vocabulary must be seeded first"
        )
    return {t.slug: t.description or "" for t in rows}


def tag_ids_by_slug(session: Session) -> dict[str, int]:
    return {t.slug: t.id for t in session.exec(select(Tag)).all() if t.id is not None}


# ─── Known URLs ──────────────────────────────────────────────────────────────


def known_urls(session: Session, urls: list[str]) -> set[str]:
    """URLs already seen — inserted as an Article, or recorded in ScoredUrl as
    fetched-but-rejected — so they are not processed twice."""
    if not urls:
        return set()
    existing = set(
        session.exec(select(Article.url).where(Article.url.in_(urls))).all()
    )
    scored = set(
        session.exec(select(ScoredUrl.url).where(ScoredUrl.url.in_(urls))).all()
    )
    return existing | scored


RecentArticle = tuple[str, str, str, list[float] | None]


def recent_articles(session: Session, days: int) -> list[RecentArticle]:
    """``(url, title, publisher_name, embedding)`` for articles published in the
    last ``days`` — the dedup window's existing stories to compare against."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = session.exec(
        select(Article.url, Article.title, Publisher.name, Article.embedding)
        .join(Publisher, Publisher.id == Article.publisher_id, isouter=True)
        .where(Article.published_at >= cutoff)
    ).all()
    return [(u, t, n or "", e) for u, t, n, e in rows]


def record_rejected(session: Session, urls: list[str]) -> None:
    """Mark URLs fetched-but-not-inserted so a later run skips them. Idempotent
    via merge on the ScoredUrl primary key."""
    if not urls:
        return
    for url in urls:
        session.merge(ScoredUrl(url=url))
    session.commit()
