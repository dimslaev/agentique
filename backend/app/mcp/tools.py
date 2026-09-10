"""The three things an agent can do against agentique: query the db, fetch a page, search the web."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date, datetime

import psycopg
from fastmcp.exceptions import ToolError

from app.platform.settings import settings
from pipeline.fetching.extract_content import fetch_and_extract
from pipeline.fetching.http import tavily_search

# A cap, not a page size: an agent that wants more should narrow the query or
# add its own LIMIT. Anything larger is context an agent cannot read anyway.
MAX_ROWS = 1000

# `user` holds emails and password hashes, and no question worth asking this
# tool needs either. The role's grants are the real boundary (see
# deploy/sql-roles.sql); the plan check below holds even where the tool runs as
# a role that has the grant anyway, which is every local database.
BLOCKED_TABLES = frozenset({"user"})

# Its own connection, not `app.platform.db` — that one logs in as POSTGRES_USER
# and would happily run a DELETE. One per call rather than a pool: the cost is
# nothing at this call rate, and no session state survives a query.
DSN = settings.MCP_DATABASE_URI


def _json_safe(value: object) -> str:
    """Fallback for the column types `json.dumps` has no encoding for.

    Timestamps get ISO-8601; Decimal, UUID and pgvector embeddings get `str`,
    which is lossless for all three and keeps one unreadable column from
    failing the whole query.
    """
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def _plan_tables(node: object) -> Iterator[str]:
    """Every table an EXPLAIN plan reads, however deeply nested.

    Walks the whole JSON rather than the top node: the table can sit under a
    join, a subplan or a CTE. Views are expanded during planning, so what comes
    back is the tables actually read, not the names the query used.
    """
    if isinstance(node, dict):
        name = node.get("Relation Name")
        if isinstance(name, str):
            yield name
        for value in node.values():
            yield from _plan_tables(value)
    elif isinstance(node, list):
        for item in node:
            yield from _plan_tables(item)


def _reject_blocked_tables(
    cursor: psycopg.Cursor[tuple[object, ...]], sql: str
) -> None:
    """Plan the statement, and refuse it if the plan reads a blocked table.

    EXPLAIN reports the tables actually read -- views expanded, joins, CTEs and
    subplans included -- and refusing to plan is what keeps this a query tool,
    since COPY, SET and DO never get that far.

    `prepare` is what makes the check honest. Given no parameters psycopg falls
    back to the simple query protocol, which runs every command in the string,
    so `SELECT 1; SELECT * FROM "user"` would be two commands and only the
    first would be the one planned here. A prepared statement takes exactly
    one, so the server rejects the second before anything executes.

    psycopg types a `str` query as LiteralString to stop callers interpolating
    input into SQL. Doing precisely that is this tool's job, hence the
    suppression; what keeps it safe is the role, this check, and `prepare`.
    """
    cursor.execute(f"EXPLAIN (FORMAT JSON) {sql}", prepare=True)  # ty: ignore[no-matching-overload]
    plan = cursor.fetchone()
    blocked = BLOCKED_TABLES.intersection(_plan_tables(plan[0] if plan else None))
    if blocked:
        raise ToolError(f"Not readable through this tool: {', '.join(sorted(blocked))}")


def sql_query(sql: str) -> str:
    """Run a read-only SQL query against the agentique Postgres database.

    Accepts one statement, and only one Postgres can plan as a query. The
    connection is a read-only transaction held by a role with SELECT grants
    only, so writes and DDL fail rather than being filtered out beforehand, and
    statements are cancelled after 10 seconds. The `user` table is not
    readable, directly or through a join. A rejected statement comes back as
    Postgres's own error message.

    Returns JSON: `columns` (in select order), `rows` (a list of objects), and
    `truncated` (true when the result hit the 1000-row cap and rows are
    missing). Timestamps are ISO-8601 strings; numerics, UUIDs and embedding
    vectors are stringified.
    """
    try:
        with psycopg.connect(DSN) as conn, conn.cursor() as cursor:
            _reject_blocked_tables(cursor, sql)

            cursor.execute(sql, prepare=True)  # ty: ignore[no-matching-overload]
            if cursor.description is None:
                # Unreachable while the plan check stands -- nothing that gets
                # past it returns without a result set. Kept as an error rather
                # than an empty result, which would read as "no rows found".
                raise ToolError("Statement returned no result set")
            columns = [column.name for column in cursor.description]
            # One past the cap, so a full page can be told from an exact fit.
            rows = cursor.fetchmany(MAX_ROWS + 1)
            return json.dumps(
                {
                    "columns": columns,
                    "rows": [
                        dict(zip(columns, row, strict=True)) for row in rows[:MAX_ROWS]
                    ],
                    "truncated": len(rows) > MAX_ROWS,
                },
                default=_json_safe,
            )
    except psycopg.Error as exc:
        # The agent wrote this SQL and can fix it, but only if it sees what
        # Postgres actually said; anything but a ToolError reaches the client
        # as a bare "internal error".
        raise ToolError(str(exc))


def web_fetch(url: str, max_length: int = 20000) -> str:
    """Fetch a web page and return its readable text, boilerplate stripped.

    Retries through a residential proxy when the direct fetch is blocked by a
    403, a paywall or a login wall. Fails if the page yields nothing readable —
    an empty string would look like an empty page rather than a failed fetch.
    """
    content = fetch_and_extract(url, max_length)
    if not content:
        raise ToolError(f"No readable content at {url}")
    return content


def web_search(
    query: str, max_results: int = 5, include_domains: list[str] | None = None
) -> list[dict[str, str | None]]:
    """Search the web (Tavily) and return ranked results.

    Each result has `title`, `url`, `description` and `published_date`
    (null unless the source dated the page). `include_domains` restricts hits
    to those hosts, e.g. `["openai.com"]` for first-party announcements only.
    """
    return tavily_search(
        query, max_results=max_results, include_domains=include_domains
    )
