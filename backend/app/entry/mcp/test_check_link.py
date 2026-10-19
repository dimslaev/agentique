"""The `check_link` tool."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.entry.mcp.check_link import check_link


@pytest.mark.usefixtures("curator")
def test_check_link_refuses_what_it_does_not_read() -> None:
    with pytest.raises(ToolError, match="web_fetch"):
        check_link("https://arxiv.org/abs/2609.01234")
