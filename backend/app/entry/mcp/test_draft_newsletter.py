"""The `draft_newsletter` tool."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.entry.mcp.draft_newsletter import draft_newsletter


def test_a_post_without_frontmatter_is_a_tool_error() -> None:
    with pytest.raises(ToolError, match="frontmatter"):
        draft_newsletter("Just an essay, no frontmatter.")
