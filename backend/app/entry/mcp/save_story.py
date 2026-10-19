"""The `save_story` tool: create a story or extend an open one.

A saved story is on the public site at once (ADR 16).
"""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.stories import service as story_domain
from app.features.stories.model import StoryError


def save_story(slug: str, name: str, blurb: str, urls: list[str]) -> str:
    """Create a story, or update an open one: set its `name` and `blurb` and
    add `urls` to it (ones already in it are skipped).

    `slug` is lowercase words joined by hyphens and never changes. `name` is
    at most 4 words, `blurb` at most 2 sentences and 280 characters. Every URL
    must be a published article and in no other open story. Any problem
    refuses the whole call, saying which, and nothing is written. A closed
    story cannot be saved to. The rail shows a story once it has 3 articles
    from 2 publishers.
    """
    require_write()
    with Session(engine) as session:
        try:
            saved = story_domain.save_story(session, slug, name, blurb, urls)
        except StoryError as exc:
            raise ToolError(str(exc))
    verb = "Created" if saved["created"] else "Updated"
    return (
        f"{verb} {saved['slug']}: added {saved['added']}, "
        f"{saved['article_count']} articles in all"
    )
