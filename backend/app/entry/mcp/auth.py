"""The bearer-token gate: two shared tokens, per-user tokens, and their scopes.

`sql_query`, `web_fetch` and `web_search` read and are reachable with
`MCP_TOKEN`. The curation tools publish and reject articles, the newsletter
tools draft emails addressed to every subscriber, and the story tools name what
the right rail shows; all of them call `require_write` first.

A token a signed-in reader made for themselves carries `USER_SCOPE` and reaches
only the tools named in `USER_TOOLS`.
"""

from __future__ import annotations

import secrets
import uuid

from anyio import to_thread
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken, AuthContext, TokenVerifier
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import AuthMiddleware
from sqlmodel import Session

from app.core.db.engine import engine
from app.core.settings import settings
from app.features.audience import service as audience

# The scope `MCP_WRITE_TOKEN` carries and the read token does not. Named for
# what it lets a caller do, not for the token that carries it.
WRITE_SCOPE = "curate"

# The scope a reader's own token carries. It marks an outside caller, so it
# narrows what the token reaches instead of adding to it.
USER_SCOPE = "user"

# The tools a `user` token may list and call. An allowlist, so a tool added to
# the server is closed to readers until it is named here. Empty for now:
# `sql_query` still logs in as the internal role and reads internal tables.
USER_TOOLS: frozenset[str] = frozenset()


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


def _user_token_owner(token: str) -> uuid.UUID | None:
    with Session(engine) as session:
        return audience.get_mcp_token_owner(session=session, token=token)


class SharedSecret(TokenVerifier):
    """Two shared bearer tokens compared in constant time, then per-user tokens.

    There are two clients — a read-only agent answering questions about the
    feed, and the curation agent that publishes to it — so an OAuth provider
    would be ceremony around two values that already live in the same `.env` as
    every other credential. The write token is checked first and is the only one
    that comes back carrying `WRITE_SCOPE`; the read token reaches the three
    reading tools and is refused by the rest.

    Anything else is hashed and looked up as a reader's own token, which comes
    back carrying `USER_SCOPE` with the account id as its client id.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        if _matches(token, settings.MCP_WRITE_TOKEN):
            return AccessToken(
                token=token, client_id="agentique-curator", scopes=[WRITE_SCOPE]
            )
        if _matches(token, settings.MCP_TOKEN):
            return AccessToken(token=token, client_id="agentique-mcp", scopes=[])
        # Off the event loop: the lookup is a blocking database call and this
        # runs on every request.
        owner = await to_thread.run_sync(_user_token_owner, token)
        if owner:
            return AccessToken(token=token, client_id=str(owner), scopes=[USER_SCOPE])
        return None


def _within_user_tools(ctx: AuthContext) -> bool:
    if ctx.token is None or USER_SCOPE not in ctx.token.scopes:
        return True
    return ctx.component.name in USER_TOOLS


# Hides every tool outside `USER_TOOLS` from a `user` token's tool list and
# refuses a call to one. Server-wide, so no tool has to remember to ask.
user_scope_gate = AuthMiddleware(auth=_within_user_tools)


def require_write() -> None:
    """Refuse a write to a caller holding only the read token."""
    token = get_access_token()
    if token is None or WRITE_SCOPE not in token.scopes:
        raise ToolError(
            "This tool needs the curation token — the read token cannot write."
        )
