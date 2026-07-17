"""HTTP for the source fetchers: a pooled client, and the Tavily search call."""

from __future__ import annotations

import threading

import httpx

from pipeline.config import residential_proxy_url, tavily_api_key

FETCH_TIMEOUT_SECS = 15.0
TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_SEARCH_CANDIDATES = 5
RESIDENTIAL_PROXY_URL = residential_proxy_url()

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
                kwargs: dict = {"follow_redirects": True}
                if proxy:
                    kwargs["proxy"] = proxy
                client = httpx.Client(**kwargs)
                _clients[proxy] = client
    return client


def fetch_with_timeout(
    url: str,
    timeout: float = FETCH_TIMEOUT_SECS,
    proxy: str | None = None,
    headers: dict | None = None,
) -> httpx.Response:
    return _get_client(proxy).get(url, timeout=timeout, headers=headers)


def tavily_search(
    query: str, max_results: int = TAVILY_SEARCH_CANDIDATES
) -> list[dict]:
    api_key = tavily_api_key()
    resp = httpx.post(
        TAVILY_SEARCH_URL,
        json={"api_key": api_key, "query": query, "max_results": max_results},
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "title": r.get("title", ""),
            "url": r["url"],
            "description": r.get("content", ""),
        }
        for r in data.get("results", [])
    ]
