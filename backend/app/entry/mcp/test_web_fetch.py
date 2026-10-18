"""`web_fetch`: what it forwards, and an empty page as an error."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.entry.mcp import web_fetch as web_fetch_tool


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
