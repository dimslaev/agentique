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
- credit an item to the publisher whose site its URL is on, when one is known,
  so a post found through an aggregator counts as its author's.
- expose the active feed publishers (rss/substack links) the pipeline should poll.
- expose the active newsletter senders (email links) the IMAP source matches.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.catalog.models import (
    LinkPlatform,
    Publisher,
    PublisherKind,
    TrustLevel,
    slugify,
)
from app.platform.logging import log
from pipeline.llm_text import enum_value
from pipeline.urls import feed_url, hostname

# ─── per-run publisher resolution ───────────────────────────────────────────


@dataclass
class PublisherResolver:
    """Resolves source names -> Publisher rows for one pipeline run.

    Caches slug -> Publisher so we hit the DB once per distinct source, and
    counts how many unknown sources we had to quarantine (surfaced in logs).
    """

    session: Session
    _cache: dict[str, Publisher] = field(default_factory=dict)
    _by_host: dict[str, Publisher] | None = None
    quarantined: list[str] = field(default_factory=list)

    def credit(self, url: str) -> Publisher | None:
        """The publisher whose site ``url`` is on, if we know one. Hacker News
        and the newsletters link to other people's posts; this is what lets
        such a post count as its author's rather than the aggregator's."""
        if self._by_host is None:
            self._by_host = hosts_to_publishers(
                self.session.exec(select(Publisher)).all()
            )
        return match_publisher(url, self._by_host)

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


# ─── crediting by URL ────────────────────────────────────────────────────────

# Hosts many unrelated authors publish under: a URL on one says nothing about
# who wrote it, so no publisher is credited from it. huggingface.co is here
# because "Hugging Face Blog" would otherwise claim every model card.
SHARED_HOSTS = frozenset(
    {
        "arxiv.org",
        "github.com",
        "huggingface.co",
        "linkedin.com",
        "medium.com",
        "reddit.com",
        "substack.com",
        "twitter.com",
        "x.com",
        "youtube.com",
    }
)

_HOST_PLATFORMS = (
    LinkPlatform.website.value,
    LinkPlatform.rss.value,
    LinkPlatform.substack.value,
)


def hosts_to_publishers(publishers: Iterable[Publisher]) -> dict[str, Publisher]:
    """Host -> the one publisher whose links name it. Pure.

    A host two publishers both claim is left out: it cannot say which of them
    wrote a given URL.
    """
    claims: dict[str, dict[int, Publisher]] = {}
    for p in publishers:
        if p.id is None:
            continue
        for platform, link in (p.links or {}).items():
            key = enum_value(platform)
            if key == LinkPlatform.search.value:
                host = link.lower().removeprefix("www.")
            elif key in _HOST_PLATFORMS:
                host = hostname(link)
            else:
                continue
            if host and host not in SHARED_HOSTS:
                claims.setdefault(host, {})[p.id] = p
    return {
        host: next(iter(pubs.values()))
        for host, pubs in claims.items()
        if len(pubs) == 1
    }


def match_publisher(url: str, by_host: dict[str, Publisher]) -> Publisher | None:
    """The publisher for a URL's host, climbing to parent domains
    (blog.example.com -> example.com) until one matches. Pure."""
    host = hostname(url)
    while "." in host:
        if host in by_host:
            return by_host[host]
        host = host.partition(".")[2]
    return None


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


def lab_watch_targets_from_db(session: Session) -> list[tuple[str, str]]:
    """Active publishers with a ``search`` link -> (name, first-party domain).

    Fallback for labs that publish no RSS feed and no newsletter: their own site
    is searched for recent first-party articles (see ``pipeline.sources.
    lab_watch``). The ``search`` value is the bare host to restrict results to.
    """
    targets = [
        (pub.name, domain)
        for pub, links in _active_publisher_links(session)
        if (domain := links.get(LinkPlatform.search.value))
    ]
    log(f"  {len(targets)} active lab-watch target(s) loaded from DB")
    return targets


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
