"""The call limit on a reader's own MCP token."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

import mcp_types as mt
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult

from app.entry.mcp.auth import USER_SCOPE

# What a reader is told: the most they can get.
LIMIT_PER_MINUTE = 20
LIMIT_PER_DAY = 500
# The backend runs this many processes (deploy/agentique-backend.service) and
# each counts on its own, so each allows its share. A reader whose calls all
# land on one worker gets half the limit.
WORKERS = 2
PER_MINUTE = LIMIT_PER_MINUTE // WORKERS
PER_DAY = LIMIT_PER_DAY // WORKERS
MINUTE = 60
DAY = 24 * 60 * 60


class UserRateLimit(Middleware):
    """At most 20 tool calls a minute and 500 a day for each `user` token.

    Counted per account, so replacing a token does not reset the count. The
    shared tokens are ours and are not limited.

    The counts live in this process. Move them to Postgres to make the limit
    exact, and change `WORKERS` if the number of workers changes.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        # Times of the calls let through in the last day, oldest first.
        self._calls: defaultdict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        """Count one call for `key`, or raise saying when to try again.

        A refused call is not counted, so retrying early does not push the
        retry time back.
        """
        now = self._clock()
        calls = self._calls[key]
        while calls and calls[0] <= now - DAY:
            calls.popleft()
        if len(calls) >= PER_DAY:
            raise _over(f"{LIMIT_PER_DAY} calls a day", calls[0] + DAY - now)
        if len(calls) >= PER_MINUTE and calls[-PER_MINUTE] > now - MINUTE:
            raise _over(
                f"{LIMIT_PER_MINUTE} calls a minute", calls[-PER_MINUTE] + MINUTE - now
            )
        calls.append(now)

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        token = get_access_token()
        if token is not None and USER_SCOPE in token.scopes:
            self.check(token.client_id)
        return await call_next(context)


def _over(limit: str, wait: float) -> ToolError:
    seconds = max(1, round(wait))
    return ToolError(f"Rate limit reached: {limit}. Retry in {seconds} seconds.")
