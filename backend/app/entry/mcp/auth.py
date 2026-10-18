"""The bearer-token gate: two tokens, and the scope only the write token carries.

`sql_query`, `web_fetch` and `web_search` read and are reachable with
`MCP_TOKEN`. The curation tools publish and reject articles, the newsletter
tools draft emails addressed to every subscriber, and the story tools name what
the right rail shows; all of them call `require_write` first.
"""

from __future__ import annotations

import secrets

from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.dependencies import get_access_token

from app.core.settings import settings

# The scope `MCP_WRITE_TOKEN` carries and the read token does not. Named for
# what it lets a caller do, not for the token that carries it.
WRITE_SCOPE = "curate"


def _matches(token: str, expected: str | None) -> bool:
    """Constant-time compare against a configured token, if there is one.

    Bytes, not str: compare_digest raises on non-ASCII str operands, and the
    token is whatever someone put in the header. An unset value matches
    nothing, so a deploy that forgets the variable serves 401s instead of an
    open database.
    """
    return bool(expected) and secrets.compare_digest(
        token.encode(), (expected or "").encode()
    )


class SharedSecret(TokenVerifier):
    """Two bearer tokens, compared in constant time, one scope between them.

    There are two clients — a read-only agent answering questions about the
    feed, and the curation agent that publishes to it — so an OAuth provider
    would be ceremony around two values that already live in the same `.env` as
    every other credential. The write token is checked first and is the only one
    that comes back carrying `WRITE_SCOPE`; the read token reaches the three
    reading tools and is refused by the rest.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        if _matches(token, settings.MCP_WRITE_TOKEN):
            return AccessToken(
                token=token, client_id="agentique-curator", scopes=[WRITE_SCOPE]
            )
        if _matches(token, settings.MCP_TOKEN):
            return AccessToken(token=token, client_id="agentique-mcp", scopes=[])
        return None


def require_write() -> None:
    """Refuse a write to a caller holding only the read token."""
    token = get_access_token()
    if token is None or WRITE_SCOPE not in token.scopes:
        raise ToolError(
            "This tool needs the curation token — the read token cannot write."
        )
