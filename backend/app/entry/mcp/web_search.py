"""The `web_search` tool: Tavily results for a query."""

from __future__ import annotations

from app.core.web_search import tavily_search


def web_search(
    query: str, max_results: int = 5, include_domains: list[str] | None = None
) -> list[dict[str, str | None]]:
    """Search the web (Tavily) and return ranked results.

    Each result has `title`, `url`, `description` and `published_date`
    (null unless the source dated the page). `include_domains` restricts hits
    to those hosts, e.g. `["openai.com"]` for first-party announcements only.
    """
    return tavily_search(
        query, max_results=max_results, include_domains=include_domains
    )
