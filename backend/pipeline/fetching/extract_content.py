"""Fetch a URL and extract its readable text (trafilatura), with a proxy retry.

The text comes back with the links the article body makes (``page_facts``), so
the one fetch serves both.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import NamedTuple

import trafilatura

from app.platform.logging import log
from pipeline.fetching.http import (
    BROWSER_HEADERS,
    RESIDENTIAL_PROXY_URL,
    fetch_with_timeout,
)
from pipeline.fetching.page_facts import outbound_links
from pipeline.urls import hostname

SKIP_DOMAINS: set[str] = {"x.com", "twitter.com"}
EXTRACT_TIMEOUT_SECS = 5.0
# The proxy adds a hop and tends to land on slower exit nodes.
PROXY_TIMEOUT_SECS = 20.0
CONCURRENCY = 5

BLOCKER_PATTERNS: list[re.Pattern] = [
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
