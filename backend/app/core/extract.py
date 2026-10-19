"""Fetch a URL and extract its readable text (trafilatura), with a proxy retry.

The text comes back with the repos, models, papers and first-party docs the
article body links, so the one fetch serves both. Only links inside the body
count: trafilatura drops the nav, footer and sidebar before the links are read,
so a "Star us on GitHub" in a site footer does not turn every post on that site
into a repo announcement.
"""

from __future__ import annotations

import html as html_lib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import NamedTuple
from urllib.parse import urljoin, urlparse, urlunparse

import trafilatura

from app.core.github import github_repo_from_url
from app.core.http import (
    BROWSER_HEADERS,
    RESIDENTIAL_PROXY_URL,
    fetch_with_timeout,
)
from app.core.logging import log
from app.core.urls import hostname, is_first_party

SKIP_DOMAINS: set[str] = {"x.com", "twitter.com"}
EXTRACT_TIMEOUT_SECS = 5.0
# The proxy adds a hop and tends to land on slower exit nodes.
PROXY_TIMEOUT_SECS = 20.0
CONCURRENCY = 5

BLOCKER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"something went wrong.*don't fret", re.IGNORECASE | re.DOTALL),
    re.compile(r"disable.*privacy\s+extensions", re.IGNORECASE),
    re.compile(r"privacy\s+extensions.*and.*retry", re.IGNORECASE),
    re.compile(r"please\s+(?:sign|log)\s*in", re.IGNORECASE),
    re.compile(r"sign\s*in\s+to\s+(?:continue|read|access)", re.IGNORECASE),
    re.compile(r"log\s*in\s+to\s+(?:continue|read|access)", re.IGNORECASE),
    re.compile(r"subscribe\s+to\s+(?:continue|read|access|unlock)", re.IGNORECASE),
    re.compile(
        r"create\s+an?\s+account\s+to\s+(?:continue|read|access)", re.IGNORECASE
    ),
    re.compile(r"enable\s+javascript\s+to\s+(?:continue|view|use)", re.IGNORECASE),
    re.compile(r"javascript\s+is\s+(?:disabled|required)", re.IGNORECASE),
    re.compile(r"access\s+denied", re.IGNORECASE),
    re.compile(r"403\s+forbidden", re.IGNORECASE),
]


class Page(NamedTuple):
    """One fetched page: its readable text and the links its body makes."""

    text: str
    links: dict[str, list[str]]


EMPTY_PAGE = Page("", {})


def _should_skip(url: str) -> bool:
    host = hostname(url)
    if not host:
        return True
    return any(host == d or host.endswith(f".{d}") for d in SKIP_DOMAINS)


def _is_blocker(text: str) -> bool:
    if len(text) < 50:
        return True
    return any(p.search(text) for p in BLOCKER_PATTERNS)


def _fetch_html(url: str, proxy: str | None = None) -> str:
    try:
        resp = fetch_with_timeout(
            url,
            timeout=PROXY_TIMEOUT_SECS if proxy else EXTRACT_TIMEOUT_SECS,
            proxy=proxy,
            headers=BROWSER_HEADERS,
        )
        if not resp.is_success:
            return ""
        ct = resp.headers.get("content-type", "")
        if "text/html" not in ct:
            return ""
        return resp.text
    except Exception:
        return ""


def extract_text(html: str, max_length: int | None = None) -> str:
    """Readable text from an HTML string, or "" if it is a blocker/teaser.

    Also used on feed-embedded HTML (``content:encoded``), so the text from a
    feed and the text from a network fetch stay comparable. Tables are kept: a
    benchmark table is often the evidence a release post rests on.
    """
    if not html:
        return ""
    text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    text = re.sub(r"\s+", " ", text).strip()
    if not text or _is_blocker(text):
        return ""
    return text[:max_length] if max_length else text


def _page(html: str, url: str, max_length: int | None) -> Page:
    text = extract_text(html, max_length)
    return Page(text, outbound_links(html, url)) if text else EMPTY_PAGE


def fetch_page(url: str, max_length: int | None = None) -> Page:
    """Fetch a URL directly, falling back to the residential proxy.

    An empty result from the direct attempt covers every failure mode we care
    about — connection error, 403/429, non-HTML body, or a paywall/login wall
    that ``_is_blocker`` caught — and all of them are worth a proxied retry.
    The proxy is metered, so it never runs first.
    """
    if _should_skip(url):
        return EMPTY_PAGE

    page = _page(_fetch_html(url), url, max_length)
    if page.text or not RESIDENTIAL_PROXY_URL:
        return page

    page = _page(_fetch_html(url, proxy=RESIDENTIAL_PROXY_URL), url, max_length)
    if page.text:
        log(f"    Proxy recovered: {url}")
    return page


def fetch_and_extract(url: str, max_length: int | None = None) -> str:
    """The readable text at a URL, or "" — ``fetch_page`` without the links."""
    return fetch_page(url, max_length).text


def _fetch_pages(
    urls: list[str], max_length: int | None = None, verbose: bool = False
) -> dict[str, Page]:
    """Fetch and extract many URLs in parallel -> {url: page}, skipping failures.

    The core of ``fetch_full_content``; logs per-URL progress when ``verbose``
    because it is the slow step.
    """
    total = len(urls)

    def one(idx_url: tuple[int, str]) -> tuple[str, Page]:
        idx, url = idx_url
        if verbose:
            log(f"    [{idx + 1}/{total}] Fetching: {url}")
        page = fetch_page(url, max_length)
        if verbose:
            size = f"OK ({len(page.text)} chars)" if page.text else "no content"
            log(f"    [{idx + 1}/{total}] {size}: {url}")
        return url, page

    pages: dict[str, Page] = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(one, pair) for pair in enumerate(urls)]
        for future in as_completed(futures):
            try:
                url, page = future.result()
                if page.text:
                    pages[url] = page
            except Exception:
                pass
    return pages


def fetch_full_content(urls: list[str]) -> dict[str, Page]:
    """Fetch the full text and links of thin items -> {url: page}."""
    if not urls:
        return {}

    unique_urls = list(dict.fromkeys(urls))
    log(f"  Re-extracting full content for {len(unique_urls)} URLs...")

    content_map = _fetch_pages(unique_urls, verbose=True)
    log(f"  Re-extracted {len(content_map)}/{len(unique_urls)} full texts")
    return content_map


# ─── Outbound links ──────────────────────────────────────────────────────────

# What one group holds at most. A survey post can link fifty papers; the agent
# needs to see what an article rests on, not its bibliography.
MAX_LINKS_PER_GROUP = 10

PAPER_HOSTS = frozenset({"arxiv.org", "openreview.net", "doi.org", "dx.doi.org"})
HF_HOSTS = frozenset({"huggingface.co", "hf.co"})
# First path segments on huggingface.co that are site pages, not a model.
HF_SITE_PAGES = frozenset(
    {
        "blog",
        "docs",
        "learn",
        "join",
        "login",
        "pricing",
        "models",
        "settings",
        "organizations",
        "collections",
        "tasks",
        "enterprise",
        "posts",
        "chat",
    }
)
GITLAB_SITE_PAGES = frozenset({"explore", "users", "help", "dashboard", "groups"})

_REF_TARGET = re.compile(r'<ref target="([^"]+)"')


def _clean(url: str, page_url: str) -> str | None:
    """Absolute http(s) URL with the fragment dropped, or None."""
    absolute = urljoin(page_url, url.strip())
    parts = urlparse(absolute)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return urlunparse(parts._replace(fragment=""))


def _same_site(a: str, b: str) -> bool:
    """True when two hosts share their last two labels (blog.x.com, docs.x.com)."""
    return bool(a and b) and a.split(".")[-2:] == b.split(".")[-2:]


def _classify(url: str, page_host: str) -> tuple[str, str] | None:
    """(group, normalized url) for one link, or None when it is in no group."""
    host = hostname(url)
    path = [p for p in urlparse(url).path.split("/") if p]

    if host == "github.com":
        repo = github_repo_from_url(url)
        return ("repo", f"https://github.com/{repo[0]}/{repo[1]}") if repo else None
    if host == "gitlab.com":
        if len(path) >= 2 and path[0].lower() not in GITLAB_SITE_PAGES:
            return "repo", f"https://gitlab.com/{path[0]}/{path[1]}"
        return None
    if host in HF_HOSTS:
        if path[:1] == ["papers"]:
            return "paper", url
        if path[:1] in (["datasets"], ["spaces"]) and len(path) >= 3:
            return "model", f"https://huggingface.co/{'/'.join(path[:3])}"
        if len(path) >= 2 and path[0].lower() not in HF_SITE_PAGES:
            return "model", f"https://huggingface.co/{path[0]}/{path[1]}"
        return ("docs", url) if is_first_party(url) else None
    if host in PAPER_HOSTS:
        return "paper", url
    if is_first_party(url) or _same_site(host, page_host):
        return "docs", url
    return None


def group_links(urls: list[str], page_url: str) -> dict[str, list[str]]:
    """Sort a page's links into repo / model / paper / docs. Pure.

    Deduped after normalizing (every blob of one repo is the repo), in the
    order the page links them, at most ``MAX_LINKS_PER_GROUP`` each. Groups
    with nothing in them are left out, and a link back to the page itself is
    not a link.
    """
    page_host = hostname(page_url)
    page = _clean(page_url, page_url)
    groups: dict[str, list[str]] = {}
    for raw in urls:
        url = _clean(raw, page_url)
        if url is None or url == page:
            continue
        hit = _classify(url, page_host)
        if hit is None:
            continue
        group, normalized = hit
        bucket = groups.setdefault(group, [])
        if normalized not in bucket and len(bucket) < MAX_LINKS_PER_GROUP:
            bucket.append(normalized)
    return groups


def outbound_links(html: str, page_url: str) -> dict[str, list[str]]:
    """The grouped links in an HTML page's article body; {} when there are none."""
    if not html:
        return {}
    xml = trafilatura.extract(
        html,
        url=page_url,
        include_links=True,
        include_tables=True,
        include_comments=False,
        output_format="xml",
    )
    if not xml:
        return {}
    targets = [html_lib.unescape(t) for t in _REF_TARGET.findall(xml)]
    return group_links(targets, page_url)
