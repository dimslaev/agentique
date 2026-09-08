"""First-party discovery for labs that publish no RSS feed, via Tavily search.

Some model labs (Anthropic, xAI, Meta, DeepSeek, Moonshot, Zhipu) don't publish
an RSS feed. Rather than depend on a third-party scraper, we ask Tavily for each
lab's recent news *restricted to the lab's own domain* (``include_domains``), so
every hit is first-party by construction.

This is a recall backstop, not an exhaustive feed: search can miss posts and
lags publication, so it complements the aggregators — it does not replace a real
feed. Watch targets are DB-driven: any active publisher carrying a ``search``
link (its bare first-party host) is polled here, mirroring how ``rss`` marks a
feed publisher and ``email`` marks a newsletter sender.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from app.platform.logging import log
from pipeline.sources.http import tavily_search
from pipeline.types import FetchedArticle
from pipeline.urls import hostname

WATCH_DAYS = 2  # nightly cadence + one missed run of slack
WATCH_CONCURRENCY = 5
RESULTS_PER_LAB = 10


def _host_is_first_party(url: str, domain: str) -> bool:
    """True if ``url``'s host is ``domain`` or a subdomain of it. Belt-and-braces
    on top of Tavily's include_domains, so a stray off-domain hit never slips in."""
    host = hostname(url)
    if not host:
        return False
    return host == domain or host.endswith(f".{domain}")


# Leading path segments that mark a non-article section — docs, reference, and
# account/marketing pages. Tavily surfaces these on lab domains and they carry
# fresh crawl dates, so date + slug checks alone let them through.
_NON_ARTICLE_SECTIONS = frozenset(
    {
        "docs",
        "doc",
        "api",
        "api-docs",
        "reference",
        "ref",
        "sdk",
        "pricing",
        "playground",
        "console",
        "help",
        "about",
        "guide",
        "guides",
        "models",
        "ai-models",
        "tags",
        "terms",
        "privacy",
        "legal",
        "careers",
        "contact",
        "login",
        "signup",
        "download",
        "downloads",
        "status",
        "support",
    }
)
# Subdomain labels that are never articles (docs.x.ai, media.x.ai, ...). Matched
# on the leftmost host label, so ``api-docs.deepseek.com`` — where DeepSeek does
# post releases under /news/ — is intentionally *not* here.
_NON_ARTICLE_HOSTS = frozenset(
    {
        "docs",
        "api",
        "developers",
        "developer",
        "media",
        "cdn",
        "static",
        "assets",
        "dashboard",
        "help",
        "support",
        "status",
    }
)
_ASSET_EXTENSIONS = (
    ".pdf",
    ".xml",
    ".json",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".mp4",
    ".csv",
    ".txt",
)


def _is_article_url(url: str) -> bool:
    """Reject anything that isn't a dated post: docs/media subdomains, asset
    files, site roots and bare section indexes, and docs/account/marketing
    sections. A real post is a slug under a content section — two-plus path
    segments whose first isn't a non-article one."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":")[0]
    if host.split(".")[0] in _NON_ARTICLE_HOSTS:
        return False
    if parsed.path.lower().endswith(_ASSET_EXTENSIONS):
        return False
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        return False
    return segments[0].lower() not in _NON_ARTICLE_SECTIONS


def _is_recent(published_date: str | None, cutoff: datetime) -> bool:
    """Keep only items dated on/after ``cutoff``. Tavily's ``days`` is unreliable
    for domain-restricted search (it returns back-catalog), and nothing
    downstream filters by date — so a missing or stale date is dropped here to
    avoid re-ingesting a lab's whole archive as if it were new."""
    if not published_date:
        return False
    try:
        dt = parsedate_to_datetime(published_date)
    except (TypeError, ValueError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt >= cutoff


def _watch_one(name: str, domain: str, cutoff: datetime) -> list[FetchedArticle]:
    query = f"{name} latest announcements, model releases, and research"
    try:
        results = tavily_search(
            query,
            max_results=RESULTS_PER_LAB,
            include_domains=[domain],
            topic="news",
            days=WATCH_DAYS,
        )
    except Exception as e:
        log(f'    Lab watch search failed for "{name}": {e}')
        return []

    articles: list[FetchedArticle] = []
    for r in results:
        if not _host_is_first_party(r["url"], domain):
            continue
        if not _is_article_url(r["url"]):
            continue
        if not _is_recent(r.get("published_date"), cutoff):
            continue
        articles.append(
            FetchedArticle(
                title=r["title"],
                url=r["url"],
                content=r["description"],
                published_date=r.get("published_date"),
                source=name,
            )
        )
    log(f"    {name}: {len(articles)} recent first-party hit(s) on {domain}")
    return articles


def fetch_lab_watch(targets: list[tuple[str, str]]) -> list[FetchedArticle]:
    """Poll each (publisher_name, first-party-domain) target concurrently.

    ``source`` on each article is the publisher name so downstream publisher
    resolution maps it back to the same active publisher row (never quarantines).
    """
    if not targets:
        log("Lab watch: no targets configured, skipping")
        return []

    log(f"Lab watch: searching {len(targets)} lab domain(s) over last {WATCH_DAYS}d")
    cutoff = datetime.now(UTC) - timedelta(days=WATCH_DAYS)
    articles: list[FetchedArticle] = []
    with ThreadPoolExecutor(max_workers=WATCH_CONCURRENCY) as ex:
        futures = [
            ex.submit(_watch_one, name, domain, cutoff) for name, domain in targets
        ]
        for f in as_completed(futures):
            articles.extend(f.result())

    log(f"Lab watch: {len(articles)} first-party articles discovered")
    return articles
