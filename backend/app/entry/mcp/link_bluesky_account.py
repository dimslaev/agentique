"""The `link_bluesky_account` tool: save a publisher's Bluesky handle."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.features.social import service as social
from app.features.social.model import SocialError


def link_bluesky_account(slug: str, handle: str) -> str:
    """Save `handle` as the publisher's Bluesky account, so `post_bluesky` can
    tag it. Follows no one. A tag notifies that account, so link only an
    account confirmed to be the publisher's."""
    with Session(engine) as session:
        try:
            return social.link_account(session, slug, handle.removeprefix("@"))
        except SocialError as exc:
            raise ToolError(str(exc))
