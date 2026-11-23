"""The `find_bluesky_account` tool: a publisher's Bluesky account, or candidates."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.features.social import service as social
from app.features.social.model import Account, SocialError


def find_bluesky_account(slug: str) -> list[Account]:
    """The publisher's Bluesky account if one is linked, else candidates to judge.

    Candidates are a handle equal to the publisher's website host, then a
    search by its name, each with bio, followers and post count. A search hit
    is not proof: link one only if its handle or bio names the publisher's
    site, or its name and bio clearly match. An empty list means none found.
    """
    with Session(engine) as session:
        try:
            return social.find_account(session, slug)
        except SocialError as exc:
            raise ToolError(str(exc))
