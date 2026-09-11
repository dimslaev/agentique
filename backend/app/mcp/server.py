"""The MCP server: the tools, the bearer-token gate, and the ASGI app `main` mounts."""

from __future__ import annotations

import secrets

from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier

from app.mcp.tools import sql_query, web_fetch, web_search
from app.platform.settings import settings


class SharedSecret(TokenVerifier):
    """One bearer token, compared in constant time.

    There is a single client — the maintainer's agent — so an OAuth provider
    would be ceremony around a value that already lives in the same `.env` as
    every other credential. An unset `MCP_TOKEN` matches nothing, so a deploy
    that forgets the variable serves 401s instead of an open database.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        expected = settings.MCP_TOKEN
        # Bytes, not str: compare_digest raises on non-ASCII str operands, and
        # the token is whatever someone put in the header.
        if not expected or not secrets.compare_digest(
            token.encode(), expected.encode()
        ):
            return None
        return AccessToken(token=token, client_id="agentique-mcp", scopes=[])


mcp: FastMCP = FastMCP(
    name="agentique",
    instructions=(
        "Tools for the agentique article pipeline: `sql_query` reads the "
        "Postgres database (publishers, articles, scores, pipeline runs), "
        "`web_fetch` reads one page, `web_search` finds pages."
    ),
    auth=SharedSecret(),
    tools=[sql_query, web_fetch, web_search],
)

# Mounted at /mcp by `app.main`, so the route inside this app is the bare root.
# Its lifespan starts the streamable-HTTP session manager and has to be handed
# to the parent app -- a mounted ASGI app never gets a lifespan of its own.
mcp_app = mcp.http_app(path="/")
