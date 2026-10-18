"""Web search through Tavily."""

from __future__ import annotations

import os

import httpx

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
TAVILY_SEARCH_CANDIDATES = 5


def tavily_search(
    query: str,
    max_results: int = TAVILY_SEARCH_CANDIDATES,
    include_domains: list[str] | None = None,
    topic: str | None = None,
    days: int | None = None,
) -> list[dict[str, str | None]]:
    """Tavily search. ``include_domains`` restricts hits to those hosts (used by
    lab_watch to guarantee first-party results); ``topic="news"`` + ``days`` ask
    for recent items and make ``published_date`` available on each result."""
    api_key = os.environ["TAVILY_API_KEY"]
    payload: dict[str, object] = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    if topic:
        payload["topic"] = topic
    if days is not None:
        payload["days"] = days
    resp = httpx.post(TAVILY_SEARCH_URL, json=payload, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    return [
        {
            "title": r.get("title", ""),
            "url": r["url"],
            "description": r.get("content", ""),
            "published_date": r.get("published_date"),
        }
        for r in data.get("results", [])
    ]
