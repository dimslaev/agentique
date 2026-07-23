"""Pooled HTTP client for feed and article fetches, with a proxy option.

One httpx.Client per proxy (``None`` = direct), reused across the whole run so
feeds and article re-fetches share connections. Timeout and headers are
per-request, so they are passed to ``get`` rather than baked into the client.
"""

from __future__ import annotations

import threading

import httpx

DIRECT_TIMEOUT_SECS = 15.0
# The proxy adds a hop and tends to land on slower exit nodes.
PROXY_TIMEOUT_SECS = 20.0

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_clients: dict[str | None, httpx.Client] = {}
_clients_lock = threading.Lock()


def _client(proxy: str | None) -> httpx.Client:
    # Fetches run from thread pools, so guard first-time creation. The client is
    # itself thread-safe for concurrent requests once built.
    client = _clients.get(proxy)
    if client is None:
        with _clients_lock:
            client = _clients.get(proxy)
            if client is None:
                kwargs: dict = {"follow_redirects": True}
                if proxy:
                    kwargs["proxy"] = proxy
                client = httpx.Client(**kwargs)
                _clients[proxy] = client
    return client


def get(url: str, proxy: str | None = None) -> httpx.Response:
    timeout = PROXY_TIMEOUT_SECS if proxy else DIRECT_TIMEOUT_SECS
    return _client(proxy).get(url, timeout=timeout, headers=BROWSER_HEADERS)
