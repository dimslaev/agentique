"""The `close_story` tool: take a story off the rail."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.stories import service as story_domain
from app.features.stories.model import StoryError


def close_story(slug: str) -> str:
    """Close an open story: it leaves the rail, and its articles are free to
    join another."""
    require_write()
    with Session(engine) as session:
        try:
            story_domain.close_story(session, slug)
        except StoryError as exc:
            raise ToolError(str(exc))
    return f"Closed {slug}"
