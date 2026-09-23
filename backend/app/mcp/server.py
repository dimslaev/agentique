"""The MCP server: the tools, the bearer-token gate, and the ASGI app `main` mounts."""

from __future__ import annotations

import secrets

from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier

from app.mcp.tools import (
    WRITE_SCOPE,
    approve,
    get_content,
    list_candidates,
    reject,
    sql_query,
    vocabulary,
    web_fetch,
    web_search,
)
from app.platform.settings import settings


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


mcp: FastMCP = FastMCP(
    name="agentique",
    instructions=(
        "Tools for the agentique article pipeline. Reading: `sql_query` reads "
        "the Postgres database (publishers, articles, scores, pipeline runs), "
        "`web_fetch` reads one page, `web_search` finds pages. Curation, with "
        "the write token only: `list_candidates` lists what is waiting on a "
        "verdict, `get_content` returns the stored text for one of them, "
        "`vocabulary` lists the labels, and `approve` and `reject` settle it."
    ),
    auth=SharedSecret(),
    tools=[
        sql_query,
        web_fetch,
        web_search,
        list_candidates,
        get_content,
        vocabulary,
        approve,
        reject,
    ],
)

# Mounted at /mcp by `app.main`, so the route inside this app is the bare root.
# Its lifespan starts the streamable-HTTP session manager and has to be handed
# to the parent app -- a mounted ASGI app never gets a lifespan of its own.
mcp_app = mcp.http_app(path="/")
