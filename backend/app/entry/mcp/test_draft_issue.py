"""The `draft_issue` tool."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.entry.mcp.draft_issue import draft_issue


@pytest.mark.usefixtures("curator")
def test_a_post_without_frontmatter_is_a_tool_error() -> None:
    with pytest.raises(ToolError, match="frontmatter"):
        draft_issue("Just an essay, no frontmatter.")
