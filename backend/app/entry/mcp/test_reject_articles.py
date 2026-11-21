"""The `reject_articles` tool."""

from __future__ import annotations

from app.entry.mcp.reject_articles import reject_articles


def test_reject_many_reports_one_line_per_verdict() -> None:
    result = reject_articles(
        [
            {"url": "https://never-queued.example/1", "score": 20, "reason": "r"},
            {"url": "https://never-queued.example/2", "score": 20, "reason": "r"},
        ]
    )
    assert result.splitlines() == [
        "Skipped https://never-queued.example/1: "
        "No candidate for https://never-queued.example/1",
        "Skipped https://never-queued.example/2: "
        "No candidate for https://never-queued.example/2",
    ]
