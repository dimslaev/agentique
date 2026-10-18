"""HTTP for the source fetchers: a pooled client and browser headers."""

from __future__ import annotations

import os
import threading

import httpx

FETCH_TIMEOUT_SECS = 15.0
# A proxy for source fetches that get blocked direct (403/429/paywall).
# Metered, so callers only reach for it after a direct attempt fails.
RESIDENTIAL_PROXY_URL = os.environ.get("RESIDENTIAL_PROXY_URL")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# Pooled clients, keyed by proxy. Building one httpx.Client per request means no
# connection reuse — HN alone fires ~201 requests. Reuse a single pooled client
# per proxy (None = direct) instead. Timeout/headers are per-request, so they are
# passed to .get() rather than baked into the client.
_clients: dict[str | None, httpx.Client] = {}
_clients_lock = threading.Lock()


def _get_client(proxy: str | None) -> httpx.Client:
    # Sources fetch from thread pools, so guard first-time creation. The client
    # itself is thread-safe for concurrent requests once built.
    client = _clients.get(proxy)
    if client is None:
        with _clients_lock:
            client = _clients.get(proxy)
            if client is None:
                client = httpx.Client(follow_redirects=True, proxy=proxy or None)
                _clients[proxy] = client
    return client


def fetch_with_timeout(
    url: str,
    timeout: float = FETCH_TIMEOUT_SECS,
    proxy: str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return _get_client(proxy).get(url, timeout=timeout, headers=headers)
