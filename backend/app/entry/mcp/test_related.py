"""The `related` tool."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.entry.mcp.related import related


@pytest.mark.usefixtures("curator")
def test_related_refuses_a_url_that_is_not_published() -> None:
    with pytest.raises(ToolError, match="No published article"):
        related("https://never-published.example/post")
