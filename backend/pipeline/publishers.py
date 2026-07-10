"""Publisher resolution + DB-driven source config.

Replaces the old hard-coded ingestion config (`run.py` SOURCES,
`sources/substack-sources.json`, `steps.py` TRUST_BY_SOURCE). Under the new
schema every article belongs to a `Publisher` row, and the set of RSS/substack
feeds to poll comes from the active publishers in the DB — not a checked-in list.

Key jobs:
- map a fetched item's ``source`` name -> a Publisher.id (via ``slugify``),
  auto-creating a *quarantined* publisher for unknown sources.
- expose the active feed publishers (rss/substack links) the pipeline should poll.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models_agentique import (
    LinkPlatform,
    Publisher,
    PublisherKind,
    TrustLevel,
    slugify,
)
from pipeline.utils import log

# ─── per-run publisher resolution ───────────────────────────────────────────


@dataclass
class PublisherResolver:
    """Resolves source names -> Publisher rows for one pipeline run.

    Caches slug -> Publisher so we hit the DB once per distinct source, and
    counts how many unknown sources we had to quarantine (surfaced in logs).
    """

    session: Session
    _cache: dict[str, Publisher] = field(default_factory=dict)
    quarantined: list[str] = field(default_factory=list)

    def resolve(self, name: str) -> Publisher:
        """Return the Publisher for ``name``, auto-creating a quarantined
        publisher (is_active=False) for an unknown source."""
        slug = slugify(name)
        cached = self._cache.get(slug)
        if cached is not None:
            return cached

        publisher = self.session.exec(
            select(Publisher).where(Publisher.slug == slug)
        ).first()

        if publisher is None:
            publisher = self._quarantine(slug, name)

        self._cache[slug] = publisher
        return publisher

    def _quarantine(self, slug: str, name: str) -> Publisher:
        """Create a placeholder publisher for an unseen source. Inactive so it
        never becomes a feed to poll, and flagged for a human to triage."""
        publisher = Publisher(
            slug=slug,
            name=name,
            kind=PublisherKind.media,  # safest default; triage can reclassify
            trust=TrustLevel.medium,
            is_active=False,  # quarantined — do not poll, do not trust
        )
        self.session.add(publisher)
        self.session.commit()
        self.session.refresh(publisher)
        self.quarantined.append(slug)
        log(f"  Quarantined new publisher: {name!r} (slug={slug}, id={publisher.id})")
        return publisher


# ─── DB-driven feed discovery ────────────────────────────────────────────────

# Which link platforms are pollable RSS-style feeds. substack feeds are RSS too.
_FEED_PLATFORMS = (LinkPlatform.rss.value, LinkPlatform.substack.value)


def _feed_url(platform: str, url: str) -> str:
    """Turn a stored link into the actual feed endpoint to poll.

    ``substack`` links are stored as the base site URL (e.g.
    ``https://foo.substack.com``, sometimes a custom domain behind it) — the
    feed itself lives at ``/feed``. ``rss`` links are stored as the direct
    feed URL already.
    """
    if platform == LinkPlatform.substack.value and not url.rstrip("/").endswith(
        "/feed"
    ):
        return url.rstrip("/") + "/feed"
    return url


def feed_sources_from_db(session: Session) -> list[dict]:
    """Active publishers with an rss/substack link -> feed configs.

    Replaces ``sources/substack-sources.json``. Shape mirrors the old JSON
    (``name`` / ``rssUrl``) so the substack fetcher needs no interface change.
    Prefers an explicit ``rss`` link, else falls back to ``substack``.
    """
    publishers = session.exec(
        select(Publisher).where(Publisher.is_active == True)  # noqa: E712
    ).all()

    sources: list[dict] = []
    for pub in publishers:
        links = pub.links or {}
        # links keys may be LinkPlatform enums or plain strings depending on the
        # JSON round-trip — normalise to string lookup.
        by_str = {str(getattr(k, "value", k)): v for k, v in links.items()}
        rss_url = None
        for platform in _FEED_PLATFORMS:
            if by_str.get(platform):
                rss_url = _feed_url(platform, by_str[platform])
                break
        if rss_url:
            sources.append({"name": pub.name, "rssUrl": rss_url})

    log(f"  {len(sources)} active feed publishers loaded from DB")
    return sources
