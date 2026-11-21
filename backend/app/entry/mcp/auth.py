"""The bearer-token gate: two shared tokens, per-user tokens, and their scopes.

The write token reaches every tool. The read token reaches only `READ_TOOLS`,
and a token a signed-in reader made for themselves only `USER_TOOLS`. Both are
allowlists checked server-wide in `scope_gate`, so a tool added to the server
is write-only until it is named in one.
"""

from __future__ import annotations

import secrets
import uuid

from anyio import to_thread
from fastmcp.server.auth import AccessToken, AuthContext, TokenVerifier
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
# the server is closed to readers until it is named here. `sql_query` is on it
# because it logs in as a narrower role for this scope.
USER_TOOLS = frozenset({"search", "tags", "sql_query"})

# The tools `MCP_TOKEN` reaches. Every other tool publishes, rejects, drafts
# email or edits the rail, and writes as `POSTGRES_USER`.
READ_TOOLS = USER_TOOLS | {"web_fetch", "web_search"}


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


def _allowed(ctx: AuthContext) -> bool:
    scopes = ctx.token.scopes if ctx.token else []
    if WRITE_SCOPE in scopes:
        return True
    allowed = USER_TOOLS if USER_SCOPE in scopes else READ_TOOLS
    return ctx.component.name in allowed


# Hides every tool a token may not call from its tool list and refuses a call
# to one. Server-wide, so no tool has to remember to ask. It skips stdio, which
# has no token; the server is only served over HTTP.
scope_gate = AuthMiddleware(auth=_allowed)
