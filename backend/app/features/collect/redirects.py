"""Point an item whose feed links through a redirect at the page it lands on.

Console's feed links every pick as ``console.dev/out/<slug>/<id>``, a 302 to
the tool's own site. Left alone, the item is credited to Console and stored
under a URL that says nothing about where it goes: UI SDK, a Vercel Labs
release, was published on 2026-11-20 as a console.dev link.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.http import BROWSER_HEADERS, fetch_with_timeout
from app.core.logging import log, short_error
from app.features.collect.model import RawItem

REDIRECT_PREFIXES = ("https://console.dev/out/",)
# The marker the redirect appends to say where the click came from.
_REF_PARAMS = {"ref"}
CONCURRENCY = 5


def is_redirect(url: str) -> bool:
    return url.startswith(REDIRECT_PREFIXES)


def without_ref(url: str) -> str:
    """``url`` without the redirect's ``ref`` marker. Pure."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in _REF_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(query)))


def _destination(url: str) -> str | None:
    try:
        final = str(fetch_with_timeout(url, headers=BROWSER_HEADERS).url)
    except Exception as e:
        log(f"  Redirect resolution failed for {url}: {short_error(e)}")
        return None
    return None if is_redirect(final) else without_ref(final)


def unwrap_redirects(articles: list[RawItem]) -> list[RawItem]:
    """Point each redirect item at its destination, in place. One that does
    not resolve keeps its redirect URL."""
    urls = [a["url"] for a in articles if is_redirect(a["url"])]
    if not urls:
        return articles
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        found = dict(zip(urls, pool.map(_destination, urls), strict=True))
    resolved = 0
    for a in articles:
        if final := found.get(a["url"]):
            a["url"] = final
            resolved += 1
    log(f"  redirects: {resolved} of {len(urls)} pointed at the page they land on")
    return articles
