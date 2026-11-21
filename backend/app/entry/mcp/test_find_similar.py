"""The `find_similar` tool."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.entry.mcp.find_similar import find_similar


def test_similar_refuses_a_url_nobody_queued() -> None:
    with pytest.raises(ToolError, match="No candidate or article for"):
        find_similar("https://never-queued.example/post")
