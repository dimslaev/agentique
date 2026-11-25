"""The `post_bluesky` tool: one public post from agentique.ch with a link card."""

from __future__ import annotations

from fastmcp.exceptions import ToolError

from app.features.social import service as social
from app.features.social.model import SocialError


def post_bluesky(text: str, url: str, title: str, description: str) -> str:
    """Post `text` publicly from agentique.ch, with a link card for `url`.

    `text` is at most 300 characters, card excluded. Each `@handle` in it
    becomes a tag that notifies that account; an unknown handle is refused.
    Each `#tag` becomes a clickable hashtag.
    `title` and `description` show on the card. A URL already posted from
    the account is refused. Returns the post's link.
    """
    try:
        return social.post(text, url, title, description)
    except SocialError as exc:
        raise ToolError(str(exc))
