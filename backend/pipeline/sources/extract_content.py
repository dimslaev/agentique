from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import trafilatura

from pipeline.sources.utils import (
    BROWSER_HEADERS,
    RESIDENTIAL_PROXY_URL,
    fetch_with_timeout,
)
from pipeline.utils import log

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
    try:
        from urllib.parse import urlparse

        host = urlparse(url).hostname or ""
        return any(host == d or host.endswith(f".{d}") for d in SKIP_DOMAINS)
    except Exception:
        return True


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


def _extract_text(html: str, max_length: int | None = None) -> str:
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

    text = _extract_text(_fetch_html(url), max_length)
    if text or not RESIDENTIAL_PROXY_URL:
        return text

    text = _extract_text(_fetch_html(url, proxy=RESIDENTIAL_PROXY_URL), max_length)
    if text:
        log(f"    Proxy recovered: {url}")
    return text


def _extract_one_snippet(url: str) -> tuple[str, str]:
    return url, _fetch_and_extract(url, SNIPPET_MAX_LENGTH)


def _extract_one_full(url: str, idx: int, total: int) -> tuple[str, str]:
    log(f"    [{idx + 1}/{total}] Fetching: {url}")
    text = _fetch_and_extract(url)
    log(
        f"    [{idx + 1}/{total}] {'OK (' + str(len(text)) + ' chars)' if text else 'no content'}: {url}"
    )
    return url, text


def extract_content(articles: list[dict]) -> list[dict]:
    """Fill in missing content snippets for a list of article dicts."""
    needs = [a for a in articles if not a.get("content")]
    if not needs:
        return articles

    unique_urls = list(dict.fromkeys(a["url"] for a in needs))
    log(f"  Extracting content for {len(unique_urls)} URLs...")

    snippet_map: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {
            executor.submit(_extract_one_snippet, url): url for url in unique_urls
        }
        for future in as_completed(futures):
            try:
                url, text = future.result()
                if text:
                    snippet_map[url] = text
            except Exception:
                pass

    log(f"  Extracted {len(snippet_map)}/{len(unique_urls)} snippets")

    result = []
    for a in articles:
        if not a.get("content") and a["url"] in snippet_map:
            result.append({**a, "content": snippet_map[a["url"]]})
        else:
            result.append(a)
    return result


def re_extract_full_content(articles: list[dict]) -> dict[str, str]:
    """Re-fetch full article text for already-inserted articles. Returns url->text map."""
    if not articles:
        return {}

    unique_urls = list(dict.fromkeys(a["url"] for a in articles))
    log(f"  Re-extracting full content for {len(unique_urls)} URLs...")

    content_map: dict[str, str] = {}
    total = len(unique_urls)

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {
            executor.submit(_extract_one_full, url, idx, total): url
            for idx, url in enumerate(unique_urls)
        }
        for future in as_completed(futures):
            try:
                url, text = future.result()
                if text:
                    content_map[url] = text
            except Exception:
                pass

    log(f"  Re-extracted {len(content_map)}/{len(unique_urls)} full texts")
    return content_map
