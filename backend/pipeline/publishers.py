"""Publisher resolution + DB-driven source config.

Replaces the old hard-coded ingestion config (`run.py` SOURCES,
`sources/substack-sources.json`, `sources/rss.py`, `email.py` NEWSLETTER_SOURCES,
`steps.py` TRUST_BY_SOURCE). Under the new schema every article belongs to a
`Publisher` row, and every source the pipeline polls — RSS/substack feeds,
IMAP newsletter senders — comes from the active publishers in the DB, not a
checked-in list.

Key jobs:
- map a fetched item's ``source`` name -> a Publisher.id (via ``slugify``),
  auto-creating a *quarantined* publisher for unknown sources.
- expose the active feed publishers (rss/substack links) the pipeline should poll.
- expose the active newsletter senders (email links) the IMAP source matches.
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
from pipeline.utils import enum_value, feed_url, log

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


def _active_publisher_links(session: Session) -> list[tuple[Publisher, dict[str, str]]]:
    """Every active publisher paired with its links keyed by platform string.

    Link keys may be LinkPlatform enums or plain strings depending on the JSON
    round-trip, so they are normalised to strings once here rather than at each
    call site.
    """
    publishers = session.exec(
        select(Publisher).where(Publisher.is_active == True)  # noqa: E712
    ).all()
    return [
        (pub, {enum_value(k): v for k, v in (pub.links or {}).items()})
        for pub in publishers
    ]


def feed_sources_from_db(session: Session) -> list[dict]:
    """Active publishers with an rss/substack link -> feed configs.

    Replaces ``sources/substack-sources.json``. Shape mirrors the old JSON
    (``name`` / ``rssUrl``) so the substack fetcher needs no interface change.
    Prefers an explicit ``rss`` link, else falls back to ``substack``.
    """
    sources: list[dict] = []
    for pub, links in _active_publisher_links(session):
        for platform in _FEED_PLATFORMS:
            url = links.get(platform)
            if url:
                sources.append(
                    {
                        "name": pub.name,
                        "rssUrl": feed_url(
                            url, is_substack=platform == LinkPlatform.substack.value
                        ),
                    }
                )
                break

    log(f"  {len(sources)} active feed publishers loaded from DB")
    return sources


# ─── DB-driven newsletter (IMAP) sender matching ───────────────────────────────


def newsletter_senders_from_db(session: Session) -> list[tuple[str, str]]:
    """Active publishers with an ``email`` link -> (sender pattern, name).

    Fallback for newsletters that don't publish an RSS feed (see
    ``feed_sources_from_db`` for those that do). The sender pattern is either
    ``@domain`` (suffix match on the From address) or an exact address.
    """
    senders = [
        (pattern, pub.name)
        for pub, links in _active_publisher_links(session)
        if (pattern := links.get(LinkPlatform.email.value))
    ]
    log(f"  {len(senders)} active newsletter senders loaded from DB")
    return senders
