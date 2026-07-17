"""Fetch a URL and extract its readable text (trafilatura), with a proxy retry."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import trafilatura

from pipeline.sources.http import (
    BROWSER_HEADERS,
    RESIDENTIAL_PROXY_URL,
    fetch_with_timeout,
)
from pipeline.types import FetchedArticle
from pipeline.utils import hostname, log

SKIP_DOMAINS: set[str] = {"x.com", "twitter.com"}
SNIPPET_MAX_LENGTH = 500
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
    feed and the text from a network fetch stay comparable.
    """
    if not html:
        return ""
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    text = re.sub(r"\s+", " ", text).strip()
    if not text or _is_blocker(text):
        return ""
    return text[:max_length] if max_length else text


def _fetch_and_extract(url: str, max_length: int | None = None) -> str:
    """Fetch a URL directly, falling back to the residential proxy.

    An empty result from the direct attempt covers every failure mode we care
    about — connection error, 403/429, non-HTML body, or a paywall/login wall
    that ``_is_blocker`` caught — and all of them are worth a proxied retry.
    The proxy is metered, so it never runs first.
    """
    if _should_skip(url):
        return ""

    text = extract_text(_fetch_html(url), max_length)
    if text or not RESIDENTIAL_PROXY_URL:
        return text

    text = extract_text(_fetch_html(url, proxy=RESIDENTIAL_PROXY_URL), max_length)
    if text:
        log(f"    Proxy recovered: {url}")
    return text


def _fetch_texts(
    urls: list[str], max_length: int | None = None, verbose: bool = False
) -> dict[str, str]:
    """Fetch and extract many URLs in parallel -> {url: text}, skipping failures.

    Shared core of ``extract_content`` (short snippets, quiet) and
    ``fetch_full_content`` (full text, logs per-URL progress because it is the
    slow step).
    """
    total = len(urls)

    def one(idx_url: tuple[int, str]) -> tuple[str, str]:
        idx, url = idx_url
        if verbose:
            log(f"    [{idx + 1}/{total}] Fetching: {url}")
        text = _fetch_and_extract(url, max_length)
        if verbose:
            size = f"OK ({len(text)} chars)" if text else "no content"
            log(f"    [{idx + 1}/{total}] {size}: {url}")
        return url, text

    texts: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(one, pair) for pair in enumerate(urls)]
        for future in as_completed(futures):
            try:
                url, text = future.result()
                if text:
                    texts[url] = text
            except Exception:
                pass
    return texts


def extract_content(articles: list[FetchedArticle]) -> list[FetchedArticle]:
    """Fill in missing content snippets for a list of article dicts."""
    needs = [a for a in articles if not a.get("content")]
    if not needs:
        return articles

    unique_urls = list(dict.fromkeys(a["url"] for a in needs))
    log(f"  Extracting content for {len(unique_urls)} URLs...")

    snippet_map = _fetch_texts(unique_urls, max_length=SNIPPET_MAX_LENGTH)
    log(f"  Extracted {len(snippet_map)}/{len(unique_urls)} snippets")

    result: list[FetchedArticle] = []
    for a in articles:
        if not a.get("content") and a["url"] in snippet_map:
            result.append({**a, "content": snippet_map[a["url"]]})
        else:
            result.append(a)
    return result


def fetch_full_content(urls: list[str]) -> dict[str, str]:
    """Fetch full article text for already-inserted articles -> {url: text}."""
    if not urls:
        return {}

    unique_urls = list(dict.fromkeys(urls))
    log(f"  Re-extracting full content for {len(unique_urls)} URLs...")

    content_map = _fetch_texts(unique_urls, verbose=True)
    log(f"  Re-extracted {len(content_map)}/{len(unique_urls)} full texts")
    return content_map
