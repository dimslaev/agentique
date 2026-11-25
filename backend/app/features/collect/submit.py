"""Hand a URL to the funnel: the steps the nightly run takes for one link.

The nightly run finds links itself. A competitor's top story it never saw has
to come in the same way, so this runs the same steps on one URL: canonicalise
it, unwrap a tweet or a redirect, drop what the run drops, refuse a known URL,
read the page for what a source would have supplied (title, text, date), credit
the publisher the URL belongs to (ADR 13) and queue a `pending` row for the
curation agent.

One step is skipped on purpose: the run's 48-hour freshness window. A
competitor's week-old top story is exactly what this is for.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from sqlmodel import Session

from app.core.db.publisher import Publisher
from app.core.extract import fetch_page
from app.core.logging import log
from app.core.urls import canonical_url, hostname
from app.features.collect.fetch import MIN_SUMMARIZABLE_CHARS, is_noise_page
from app.features.collect.filter import filter_known_urls, filter_thin_repos
from app.features.collect.model import Candidate, QueueError, RawItem
from app.features.collect.publishers import PublisherResolver
from app.features.collect.queue import queue_candidates
from app.features.collect.redirects import unwrap_redirects
from app.features.collect.tweets import unwrap_tweets

# Where the link was found. Becomes `Article.found_via` on approval, next to
# "Hacker News" and the newsletters, and names no publisher.
COMPETITOR_SOURCE = "Competitor watch"


def _http_url(url: str) -> str:
    url = url.strip()
    if urlsplit(url).scheme not in ("http", "https") or not hostname(url):
        raise QueueError(f"{url!r} is not an http(s) URL")
    return canonical_url(url)


def _require_reason(reason: str) -> str:
    reason = reason.strip()
    if not reason:
        raise QueueError("Give the reason: the competitor and where it ran the story")
    return reason


def _landing(item: RawItem) -> str:
    """Where ``item`` lands once the run's unwrapping is done, refused if the
    run would drop it. Updates ``item`` in place."""
    unwrap_redirects(unwrap_tweets([item]))
    item["url"] = canonical_url(item["url"])
    if is_noise_page(item["url"]):
        raise QueueError(f"{item['url']} is an event or reference page")
    return item["url"]


def _item(url: str, reason: str) -> RawItem:
    return {
        "title": "",
        "url": url,
        "content": "",
        "published_date": None,
        "source": COMPETITOR_SOURCE,
        "traction": reason,
    }


def _require_new(session: Session, item: RawItem) -> None:
    if not filter_known_urls(session, [item], COMPETITOR_SOURCE):
        raise QueueError(f"{item['url']} is already known")


def queue_link(session: Session, url: str, reason: str) -> tuple[Candidate, Publisher]:
    """Queue ``url`` as a pending candidate found through a competitor, and
    return it with the publisher it was credited to.

    ``reason`` says which competitor led here and how; the curation agent reads
    it as the candidate's traction. Raises `QueueError` for a URL we already
    know, one the run would drop, a page with no readable text or title, a
    site that names no publisher, and a GitHub repo under the star floor.
    """
    reason = _require_reason(reason)
    url = _http_url(url)
    item = _item(url, reason)
    _require_new(session, item)
    # A link the pipeline would have unwrapped is known by where it lands.
    if _landing(item) != url:
        _require_new(session, item)

    page = fetch_page(item["url"], meta=True)
    if len(page.text.strip()) < MIN_SUMMARIZABLE_CHARS:
        raise QueueError(f"No readable text at {item['url']}")
    if not page.title:
        raise QueueError(f"No title found at {item['url']}")
    item["title"], item["content"] = page.title, page.text
    item["published_date"], item["links"] = page.published, page.links

    resolver = PublisherResolver(session=session)
    publisher = resolver.credit(item["url"]) or resolver.author(item["url"])
    if publisher is None or publisher.id is None:
        raise QueueError(f"{item['url']} is on a shared host that names no publisher")
    candidate: Candidate = {**item, "publisher_id": publisher.id}

    if not filter_thin_repos(session, [candidate], COMPETITOR_SOURCE):
        raise QueueError(f"{item['url']} is a GitHub repo under the star floor")
    [queued] = queue_candidates(session, [candidate])
    return queued, publisher


def add_publisher(session: Session, url: str, reason: str) -> tuple[Publisher, bool]:
    """The publisher ``url`` belongs to, and whether this call made it.

    A known site returns its publisher as it is, active or not. A new one is
    made as the nightly run makes it: inactive, with only a `website` link, its
    kind `unknown` until the curation agent names it. A shortener, a tweet or
    an event page is refused the way `queue_link` refuses it, so no publisher
    is made for a tracker or a sign-up host. ``reason`` goes to the log: the
    publisher has no column for it.
    """
    reason = _require_reason(reason)
    url = _landing(_item(_http_url(url), reason))
    resolver = PublisherResolver(session=session)
    known = resolver.credit(url)
    if known is not None:
        return known, False
    publisher = resolver.author(url)
    if publisher is None:
        raise QueueError(f"{url} is on a shared host that names no publisher")
    log(f"  add_publisher {publisher.slug}: {reason}")
    return publisher, True
