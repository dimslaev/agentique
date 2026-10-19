"""`web_search`: what it forwards."""

from __future__ import annotations

import pytest

from app.entry.mcp import web_search as web_search_tool


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
