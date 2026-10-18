"""`web_fetch` and `web_search`: what they forward, and an empty page as an error."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.entry.mcp import web_fetch as web_fetch_tool
from app.entry.mcp import web_search as web_search_tool


def test_web_fetch_returns_extracted_text_and_forwards_the_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, int]] = []

    def fake(url: str, max_length: int) -> str:
        seen.append((url, max_length))
        return f"text of {url}"

    monkeypatch.setattr(web_fetch_tool, "fetch_and_extract", fake)
    text = web_fetch_tool.web_fetch("https://example.com/post", max_length=50)
    assert text == "text of https://example.com/post"
    assert seen == [("https://example.com/post", 50)]


def test_web_fetch_fails_loudly_when_nothing_is_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(web_fetch_tool, "fetch_and_extract", lambda url, max_length: "")
    with pytest.raises(ToolError, match="No readable content"):
        web_fetch_tool.web_fetch("https://example.com/paywalled")


def test_web_search_forwards_every_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int, list[str] | None]] = []

    def fake(
        query: str, max_results: int, include_domains: list[str] | None
    ) -> list[dict[str, str | None]]:
        calls.append((query, max_results, include_domains))
        return [{"title": "t", "url": "u", "description": "d", "published_date": None}]

    monkeypatch.setattr(web_search_tool, "tavily_search", fake)
    results = web_search_tool.web_search(
        "gpt-5", max_results=3, include_domains=["openai.com"]
    )
    assert calls == [("gpt-5", 3, ["openai.com"])]
    assert results[0]["url"] == "u"
