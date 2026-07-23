"""Extract readable text — from feed-embedded HTML, or from the live page.

The same trafilatura pass runs on both a feed's ``content:encoded`` and a
network fetch, so text from either source is comparable and the same blocker
detection (login/paywall walls, teasers) applies to both. That is what lets the
pipeline trust feed content and only reach for the network when it is thin.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import trafilatura

from pipeline_new import http
from pipeline_new.config import residential_proxy_url
from pipeline_new.util import hostname, log

# Bodies these hosts serve are never article text worth extracting.
SKIP_DOMAINS: set[str] = {"x.com", "twitter.com"}
CONCURRENCY = 5

BLOCKER_PATTERNS: list[re.Pattern] = [
    re.compile(r"something went wrong.*don't fret", re.IGNORECASE | re.DOTALL),
    re.compile(r"disable.*privacy\s+extensions", re.IGNORECASE),
    re.compile(r"privacy\s+extensions.*and.*retry", re.IGNORECASE),
    re.compile(r"please\s+(?:sign|log)\s*in", re.IGNORECASE),
    re.compile(r"sign\s*in\s+to\s+(?:continue|read|access)", re.IGNORECASE),
    re.compile(r"log\s*in\s+to\s+(?:continue|read|access)", re.IGNORECASE),
    re.compile(r"subscribe\s+to\s+(?:continue|read|access|unlock)", re.IGNORECASE),
    re.compile(r"create\s+an?\s+account\s+to\s+(?:continue|read|access)", re.IGNORECASE),
    re.compile(r"enable\s+javascript\s+to\s+(?:continue|view|use)", re.IGNORECASE),
    re.compile(r"javascript\s+is\s+(?:disabled|required)", re.IGNORECASE),
    re.compile(r"access\s+denied", re.IGNORECASE),
    re.compile(r"403\s+forbidden", re.IGNORECASE),
]


def _is_blocker(text: str) -> bool:
    """A teaser (under 50 chars) or a wall message is not article content."""
    if len(text) < 50:
        return True
    return any(p.search(text) for p in BLOCKER_PATTERNS)


def extract_text(html: str) -> str:
    """Readable plain text from an HTML string, or "" if it is a blocker/teaser.

    Used on both feed HTML and fetched pages, so their text stays comparable.
    """
    if not html:
        return ""
    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    text = re.sub(r"\s+", " ", text).strip()
    if not text or _is_blocker(text):
        return ""
    return text


def _should_skip(url: str) -> bool:
    host = hostname(url)
    if not host:
        return True
    return any(host == d or host.endswith(f".{d}") for d in SKIP_DOMAINS)


def _fetch_html(url: str, proxy: str | None) -> str:
    try:
        resp = http.get(url, proxy=proxy)
        if not resp.is_success:
            return ""
        if "text/html" not in resp.headers.get("content-type", ""):
            return ""
        return resp.text
    except Exception:
        return ""


def fetch_readable(url: str) -> str:
    """Fetch a URL's readable text, direct first then via the residential proxy.

    An empty direct result covers every failure we care about — connection
    error, 403/429, non-HTML body, or a wall ``_is_blocker`` caught — and each
    is worth a proxied retry. The proxy is metered, so it never runs first.
    """
    if _should_skip(url):
        return ""

    text = extract_text(_fetch_html(url, proxy=None))
    proxy = residential_proxy_url()
    if text or not proxy:
        return text

    text = extract_text(_fetch_html(url, proxy=proxy))
    if text:
        log(f"    Proxy recovered content: {url}")
    return text


def fetch_readable_many(urls: list[str]) -> dict[str, str]:
    """Fetch readable text for many URLs in parallel -> {url: text}, dropping
    failures. Only the URLs whose feed content was too thin ever get here."""
    if not urls:
        return {}
    unique = list(dict.fromkeys(urls))
    log(f"  Re-fetching full content for {len(unique)} thin article(s)...")

    out: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(fetch_readable, u): u for u in unique}
        for future in as_completed(futures):
            url = futures[future]
            try:
                text = future.result()
            except Exception:
                text = ""
            if text:
                out[url] = text
    log(f"  Recovered {len(out)}/{len(unique)} full texts")
    return out
