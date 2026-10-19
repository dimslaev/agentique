"""The `reject_many` tool."""

from __future__ import annotations

import pytest

from app.entry.mcp.reject_many import reject_many


@pytest.mark.usefixtures("curator")
def test_reject_many_reports_one_line_per_verdict() -> None:
    result = reject_many(
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
