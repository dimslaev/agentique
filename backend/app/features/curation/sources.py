"""Source discovery: which inactive publishers are worth probing, which active
feeds have stopped earning their place, and the writes that switch them.

HN and the newsletters find new sites and leave each one an inactive publisher
with only a website link. The discovery agent reads their recent posts against
the curate rubric and turns on the ones that pass, so the pipeline polls them
directly. It never publishes: curate stays the only judge of articles. The
thresholds here are what the skill's verdicts are checked against in code, so
a sloppy session cannot switch on a dead or noisy feed.
"""

from __future__ import annotations

import calendar
import time
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin

import feedparser  # type: ignore[import-untyped]
from sqlmodel import Session, col, func, select

from app.core.db.article import Article
from app.core.db.ledger import Reject
from app.core.db.publisher import (
    AGGREGATOR_TYPES,
    LinkPlatform,
    Publisher,
    PublisherKind,
    PublisherType,
)
from app.core.http import BROWSER_HEADERS, RESIDENTIAL_PROXY_URL, fetch_with_timeout
from app.core.llm_text import enum_value
from app.core.logging import log
from app.core.urls import hostname, is_shared_host
from app.features.curation.model import SourceError

# How many of a site's newest posts a probe reads at most.
PROBE_POSTS = 10
ACTIVATE_MIN_RATE = 0.4
# A feed with no post this recent is dead; switching it on would poll nothing.
RECENT_POST_DAYS = 90
CULL_MIN_DECISIONS = 10
# One lucky approval kept a firehose polled for months (aifeed.dev at 1/366):
# under this rate, over enough decisions, a feed goes off too.
CULL_MAX_RATE = 0.05
CULL_RATE_MIN_DECISIONS = 30
CULL_SILENT_DAYS = 120
FEED_PATHS = ("/feed", "/rss.xml", "/atom.xml", "/index.xml", "/feed.xml", "/rss")
_FEED_TYPES = ("application/rss+xml", "application/atom+xml")
_BLOCKED = (401, 403, 429)
# Stop trying candidate paths here: the MCP client gives a tool 120s, and a
# site that hangs costs two 15s timeouts per path.
FIND_FEED_SECS = 75
_SEARCH_KINDS = (PublisherKind.lab, PublisherKind.company)


def can_reach_rate(approved: int, rejected: int) -> bool:
    """Whether a full probe of passes could still lift the publisher to
    `ACTIVATE_MIN_RATE`. Keeps firehoses out of the pool without spending a
    probe on them. Pure."""
    return approved + PROBE_POSTS >= ACTIVATE_MIN_RATE * (
        approved + rejected + PROBE_POSTS
    )


def reopened(switched_at: datetime | None, last_approval: datetime | None) -> bool:
    """Whether a deactivated publisher is back in the pool: only on an approval
    after the agent switched it off. One a person switched off has no
    `switched_at` and stays off. Pure."""
    return (
        switched_at is not None
        and last_approval is not None
        and last_approval > switched_at
    )


def deactivate_reason(
    approved: int, rejected: int, silent_since: datetime, now: datetime
) -> str | None:
    """Why an active feed should go off, or None to keep it. Pure."""
    decisions = approved + rejected
    if approved == 0 and rejected >= CULL_MIN_DECISIONS:
        return f"culled 0/{rejected} 90d {now.date()}"
    if decisions >= CULL_RATE_MIN_DECISIONS and approved < CULL_MAX_RATE * decisions:
        return f"culled {approved}/{decisions} 90d {now.date()}"
    if silent_since < now - timedelta(days=CULL_SILENT_DAYS):
        return f"culled silent since {silent_since.date()} {now.date()}"
    return None


def _links(p: Publisher) -> dict[str, str]:
    return {enum_value(k): v for k, v in (p.links or {}).items()}


def _rate(approved: int, rejected: int) -> str:
    return f"{approved}/{approved + rejected}"


def review_publishers(
    session: Session,
    approval_counts: dict[int, tuple[int, int]],
    limit: int,
    now: datetime,
) -> dict[str, list[dict[str, str]]]:
    """`probe`: up to `limit` inactive publishers with an approval in the
    window, a website, a rate a probe can still lift, and no standing
    deactivation reason; the most approvals first. `deactivate`: every active feed
    publisher that `deactivate_reason` turns down, with the reason to write."""
    publishers = session.exec(select(Publisher)).all()
    last_approval = dict(
        session.exec(
            select(col(Article.publisher_id), func.max(Article.created_at)).group_by(
                col(Article.publisher_id)
            )
        ).all()
    )
    probe: list[tuple[int, float, dict[str, str]]] = []
    deactivate: list[dict[str, str]] = []
    for p in publishers:
        assert p.id is not None
        approved, rejected = approval_counts.get(p.id, (0, 0))
        links = _links(p)
        row = {
            "slug": p.slug,
            "name": p.name,
            "kind": p.kind.value,
            "approved": _rate(approved, rejected),
        }
        if p.is_active:
            # An aggregator's approvals are credited to the sites it links
            # to, so its own count says nothing about what it is worth.
            if p.type in AGGREGATOR_TYPES or not (
                links.get("rss") or links.get("substack")
            ):
                continue
            # Silent since its last new post, or since it was switched on.
            marks = [d for d in (p.last_new_at, p.switched_at) if d]
            silent = max(marks) if marks else p.created_at
            reason = deactivate_reason(approved, rejected, silent, now)
            if reason:
                deactivate.append({**row, "reason": reason})
            continue
        website = links.get(LinkPlatform.website.value)
        last = last_approval.get(p.id)
        if (
            approved >= 1
            and website
            and not is_shared_host(hostname(website))
            and can_reach_rate(approved, rejected)
            and (p.disabled_reason is None or reopened(p.switched_at, last))
        ):
            row |= {
                "website": website,
                "last_approval": last.date().isoformat() if last else "",
                "disabled_reason": p.disabled_reason or "",
            }
            probe.append((approved, approved / (approved + rejected), row))
    probe.sort(key=lambda t: (-t[0], -t[1], t[2]["slug"]))
    return {"probe": [row for *_, row in probe[:limit]], "deactivate": deactivate}


class _Alternates(HTMLParser):
    """Collects `<link rel="alternate" type="application/rss+xml" href>`."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if (
            tag == "link"
            and "alternate" in (a.get("rel") or "").lower().split()
            and (a.get("type") or "").lower() in _FEED_TYPES
            and a.get("href")
        ):
            self.hrefs.append(a["href"] or "")


def feed_links(html: str, base: str) -> list[str]:
    """Feed URLs a page declares, then the common paths, deduplicated. Pure."""
    parser = _Alternates()
    parser.feed(html)
    found = [urljoin(base, h) for h in parser.hrefs]
    found += [urljoin(base, p) for p in FEED_PATHS]
    return list(dict.fromkeys(found))


def _get(url: str) -> bytes:
    """The body at `url`, retried through the residential proxy when the
    direct fetch fails or is blocked (Substack blocks the box's IP), or b"" if
    neither answers. A plain 404 is not retried."""
    for proxy in dict.fromkeys((None, RESIDENTIAL_PROXY_URL)):
        try:
            resp = fetch_with_timeout(url, proxy=proxy, headers=BROWSER_HEADERS)
        except Exception:
            continue
        if resp.is_success:
            return resp.content
        if resp.status_code not in _BLOCKED:
            break
    return b""


def _published(entry: dict[str, object]) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), UTC)  # type: ignore[arg-type]


def read_feed(url: str) -> list[dict[str, object]]:
    """A feed's entries, newest first: `title`, `link`, `published` (or None).
    Empty when `url` is not a feed."""
    return _entries(feedparser.parse(_get(url)))


def _entries(parsed: feedparser.FeedParserDict) -> list[dict[str, object]]:
    entries = [
        {
            "title": e.get("title", ""),
            "link": e.get("link", ""),
            "published": _published(e),
        }
        for e in parsed.entries
        if e.get("link")
    ]
    epoch = datetime.min.replace(tzinfo=UTC)
    entries.sort(key=lambda e: e["published"] or epoch, reverse=True)
    return entries


def find_feed(session: Session, url: str) -> dict[str, object] | None:
    """The first feed at `url` (itself a feed, a declared alternate, or a
    common path) with its newest `PROBE_POSTS` entries, each marked with what
    agentique already decided about it. A feed that parses but lists nothing
    today (arXiv at the weekend) comes back with no entries. None if no feed
    answers within `FIND_FEED_SECS`."""
    deadline = time.monotonic() + FIND_FEED_SECS
    candidates = [url, *feed_links(_get(url).decode("utf-8", "replace"), url)]
    empty = None
    for candidate in dict.fromkeys(candidates):
        if time.monotonic() > deadline:
            break
        parsed = feedparser.parse(_get(candidate))
        entries = _entries(parsed)[:PROBE_POSTS]
        if entries:
            return {"feed_url": candidate, "entries": _judged(session, entries)}
        if empty is None and parsed.get("version"):
            empty = candidate
    return {"feed_url": empty, "entries": []} if empty else None


def _judged(session: Session, entries: list[dict[str, object]]) -> list[dict[str, str]]:
    links = [str(e["link"]) for e in entries]
    approved = set(
        session.exec(select(Article.url).where(col(Article.url).in_(links))).all()
    )
    stages = dict(
        session.exec(
            select(Reject.url, Reject.stage).where(col(Reject.url).in_(links))
        ).all()
    )
    out = []
    for e in entries:
        link, published = str(e["link"]), e["published"]
        if link in approved:
            judged = "approved"
        else:
            judged = enum_value(stages[link]) if link in stages else ""
        out.append(
            {
                "title": str(e["title"]),
                "link": link,
                "published": published.date().isoformat()  # type: ignore[attr-defined]
                if published
                else "",
                "judged": judged,
            }
        )
    return out


def _publisher(session: Session, slug: str) -> Publisher:
    p = session.exec(select(Publisher).where(Publisher.slug == slug)).first()
    if p is None:
        raise SourceError(f"No publisher {slug}")
    return p


def activate_publisher(
    session: Session,
    slug: str,
    feed_url: str | None,
    search_domain: str | None,
    reason: str,
    now: datetime,
) -> str:
    """Switch an inactive publisher on, polled through `feed_url` or, for a lab
    or company with no feed, searched on `search_domain`. Refuses a feed that
    does not parse or has no post in `RECENT_POST_DAYS`."""
    p = _publisher(session, slug)
    if p.is_active:
        raise SourceError(f"{slug} is already active")
    if not reason.strip():
        raise SourceError("Give the reason, with the numbers")
    if (feed_url is None) == (search_domain is None):
        raise SourceError("Pass exactly one of feed_url and search_domain")
    links = _links(p)
    if feed_url is not None:
        dates = [e["published"] for e in read_feed(feed_url) if e["published"]]
        if not dates:
            raise SourceError(f"No dated entries at {feed_url}")
        newest: datetime = max(dates)  # type: ignore[type-var,assignment]
        if newest < now - timedelta(days=RECENT_POST_DAYS):
            raise SourceError(f"Newest post at {feed_url} is from {newest.date()}")
        is_substack = hostname(feed_url).endswith("substack.com")
        platform = LinkPlatform.substack if is_substack else LinkPlatform.rss
        p.type = PublisherType.substack if is_substack else PublisherType.rss
        links[platform.value] = feed_url
    else:
        if p.kind not in _SEARCH_KINDS:
            raise SourceError(
                f"Search is for labs and companies, {slug} is {p.kind.value}"
            )
        domain = (search_domain or "").lower().removeprefix("www.")
        site = hostname(links.get(LinkPlatform.website.value, ""))
        if not site or not (site == domain or site.endswith(f".{domain}")):
            raise SourceError(f"{domain} is not {slug}'s site ({site or 'none'})")
        p.type = PublisherType.search
        links[LinkPlatform.search.value] = domain
    p.links = {LinkPlatform(k): v for k, v in links.items()}
    p.is_active = True
    p.disabled_reason = None
    p.switched_at = now
    session.add(p)
    session.commit()
    log(f"  Activated {slug} ({p.type.value}): {reason}")
    return f"Activated {slug} as {p.type.value}"


def deactivate_publisher(
    session: Session, slug: str, reason: str, now: datetime
) -> str:
    """Switch a publisher off, or mark an inactive one as probed and failed, so
    it stays out of the pool until a newer approval."""
    if not reason.strip():
        raise SourceError("Give the reason, with the numbers")
    p = _publisher(session, slug)
    p.is_active = False
    p.disabled_reason = reason.strip()
    p.switched_at = now
    session.add(p)
    session.commit()
    log(f"  Deactivated {slug}: {reason}")
    return f"Deactivated {slug}"
