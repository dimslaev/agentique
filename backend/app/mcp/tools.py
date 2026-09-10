"""The three things an agent can do against agentique: query the db, fetch a page, search the web."""

from __future__ import annotations

import json
from datetime import date, datetime

from fastmcp.exceptions import ToolError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlmodel import create_engine

from app.platform.settings import settings
from pipeline.fetching.extract_content import fetch_and_extract
from pipeline.fetching.http import tavily_search

# A cap, not a page size: an agent that wants more should narrow the query or
# add its own LIMIT. Anything larger is context an agent cannot read anyway.
MAX_ROWS = 1000

# Its own engine, on the read-only DSN — the request-scoped `app.platform.db`
# engine logs in as POSTGRES_USER and would happily run a DELETE.
engine = create_engine(settings.MCP_DATABASE_URI, pool_pre_ping=True)


def _json_safe(value: object) -> str:
    """Fallback for the column types `json.dumps` has no encoding for.

    Timestamps get ISO-8601; Decimal, UUID and pgvector embeddings get `str`,
    which is lossless for all three and keeps one unreadable column from
    failing the whole query.
    """
    if isinstance(value, datetime | date):
        return value.isoformat()
    return str(value)


def sql_query(sql: str) -> str:
    """Run a read-only SQL query against the agentique Postgres database.

    Accepts any statement, but the connection is a read-only transaction held
    by a role with SELECT grants only, so writes and DDL fail rather than being
    filtered out beforehand. Statements are cancelled after 10 seconds. A
    rejected statement comes back as Postgres's own error message.

    Returns JSON: `columns` (in select order), `rows` (a list of objects), and
    `truncated` (true when the result hit the 1000-row cap and rows are
    missing). Timestamps are ISO-8601 strings; numerics, UUIDs and embedding
    vectors are stringified.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            if not result.returns_rows:
                return json.dumps({"columns": [], "rows": [], "truncated": False})
            columns = list(result.keys())
            # One past the cap, so a full page can be told from an exact fit.
            rows = result.fetchmany(MAX_ROWS + 1)
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
    except SQLAlchemyError as exc:
        # The agent wrote this SQL and can fix it, but only if it sees what
        # Postgres actually said; anything but a ToolError reaches the client
        # as a bare "internal error".
        cause = exc.orig if isinstance(exc, DBAPIError) else None
        raise ToolError(str(cause or exc))


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
