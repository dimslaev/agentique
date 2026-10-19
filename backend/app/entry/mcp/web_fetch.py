"""The `web_fetch` tool: one page as readable text."""

from __future__ import annotations

from fastmcp.exceptions import ToolError

from app.core.extract import fetch_and_extract


def web_fetch(url: str, max_length: int = 20000) -> str:
    """Fetch a web page and return its readable text, boilerplate stripped.

    Retries through a residential proxy when the direct fetch is blocked by a
    403, a paywall or a login wall. Fails if the page yields nothing readable —
    an empty string would look like an empty page rather than a failed fetch.
    """
    content = fetch_and_extract(url, max_length)
    if not content:
        raise ToolError(f"No readable content at {url}")
    return content
