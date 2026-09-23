"""What an agent can do against agentique: read the db and the web, and curate.

Two groups, two tokens. `sql_query`, `web_fetch` and `web_search` read and are
reachable with `MCP_TOKEN`. The curation tools at the bottom publish and reject
articles, and need `MCP_WRITE_TOKEN` — see `WRITE_SCOPE` below.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date, datetime

import psycopg
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token
from sqlmodel import Session

from app.platform.db import engine
from app.platform.settings import settings
from pipeline import curation
from pipeline.fetching import page_facts
from pipeline.fetching.extract_content import fetch_and_extract
from pipeline.fetching.http import tavily_search

# The scope `MCP_WRITE_TOKEN` carries and the read token does not. Named for
# what it lets a caller do, not for the token that carries it: `server.py` mints
# it, the curation tools below demand it.
WRITE_SCOPE = "curate"

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


# ─── Curation ────────────────────────────────────────────────────────────────
# The verbs the curation agent drives the pipeline's tail with. Some write and
# all of them read the queue, so each one checks for the write scope first: the
# read token reaches `sql_query`, `web_fetch` and `web_search` and nothing else.


def _require_write() -> None:
    """Refuse a write to a caller holding only the read token."""
    token = get_access_token()
    if token is None or WRITE_SCOPE not in token.scopes:
        raise ToolError(
            "This tool needs the curation token — the read token cannot write."
        )


def _curation_session() -> Session:
    """A read/write session, not the read-only DSN `sql_query` uses."""
    return Session(engine)


def list_candidates() -> list[dict[str, str]]:
    """List the articles waiting on a curation verdict, freshest first.

    One row per candidate: `url`, `title`, `source` (where the link was found),
    `publisher`, `trust`, `traction`, `published_at`, `queued_at`, and a
    200-character `snippet`. Deliberately not the full text — call
    `get_content` for a candidate worth a closer look.

    A candidate stays listed until `approve` or `reject` is called on it, so a
    session that stops halfway leaves the rest for the next one.
    """
    _require_write()
    with _curation_session() as session:
        return curation.list_candidates(session)


def get_content(
    url: str, offset: int = 0, limit: int = curation.PAGE_LIMIT
) -> curation.ContentPage:
    """Return one page of the article text the pipeline extracted for a candidate.

    The stored text is what a page fetch returns, cut at 12000 characters, so
    read here first. Returns `text`, `offset`, `next_offset` (null on the last
    page — pass it back as `offset` to read on), `total` characters, and, on
    the first page only, `links`: the repo / model / paper / docs URLs the
    article body links, grouped. Fetch the page only when this is empty, a
    teaser, or cut off before the part you need.
    """
    _require_write()
    with _curation_session() as session:
        try:
            return curation.get_content(session, url, offset, limit)
        except curation.CandidateError as exc:
            raise ToolError(str(exc))


def similar(url: str, days: int = 7, limit: int = 8) -> curation.Similar:
    """Show what the feed and the ledger hold that is close to one candidate.

    Compares by embedding against every published article and every candidate
    or reject from the last `days`. `rows` lists up to `limit` neighbours, the
    closest first: `url`, `title`, `publisher`, `stage` (`published`,
    `pending`, or the reject stage), `score` and `distance` (under 0.30 is the
    same story). `coverage` is how many distinct publishers carry this story,
    this candidate's own included, with their names in `publishers`.
    """
    _require_write()
    with _curation_session() as session:
        try:
            return curation.similar(session, url, days, limit)
        except curation.CandidateError as exc:
            raise ToolError(str(exc))


def stories(days: int = 7) -> list[curation.Story]:
    """Group the pending candidates that are one story, with each other or with
    an article published in the last `days`.

    Only groups of two or more come back, largest first, each with its
    `members` (same row shape as `similar`, without the distance), `coverage`
    (distinct publishers) and `publishers`. A member at stage `published`
    means the feed already carries the story. Call it once, after triage.
    """
    _require_write()
    with _curation_session() as session:
        return curation.stories(session, days)


def check_link(url: str) -> dict[str, object]:
    """Look up a GitHub or GitLab repo, or a Hugging Face model or dataset.

    Repos: `stars`, `forks`, `last_push`, `license`, `archived`, `has_readme`,
    `description`. Models and datasets: `downloads`, `likes`, `last_modified`,
    `license`, `files` (count), and for a model `weights` (true when weight
    files are present). A value the lookup could not get reads `unknown`, never
    0; `lookup: unknown` means the whole lookup failed. Any other URL is
    refused — read it with `web_fetch`.
    """
    _require_write()
    try:
        return page_facts.check_link(url)
    except page_facts.LinkError as exc:
        raise ToolError(str(exc))


def vocabulary() -> dict[str, object]:
    """The labels `approve` accepts: `categories`, `kinds`, and `tags` as
    slug -> description. Call it once per session, before the first approve."""
    _require_write()
    with _curation_session() as session:
        return curation.vocabulary(session)


def approve(
    url: str,
    score: int,
    reason: str,
    summary: str,
    categories: list[str],
    kind: str,
    tags: list[str],
) -> str:
    """Publish a candidate with the labels you chose, then embed it.

    `score` is 1-100 on the same scale the rubric describes, `reason` one short
    sentence naming what decided it, and `summary` the text a reader sees under
    the title. `categories` (one or more), `kind` and `tags` (up to 3) come from
    `vocabulary`; a github, huggingface or arxiv URL sets its own kind. A label
    that is not in the vocabulary is refused and the candidate stays pending.
    The candidate stops being pending in the same transaction that inserts the
    article, so nothing is ever published twice.
    """
    _require_write()
    with _curation_session() as session:
        try:
            article_id = curation.approve(
                session, url, score, reason, summary, categories, kind, tags
            )
        except curation.CandidateError as exc:
            raise ToolError(str(exc))
    return f"Published article #{article_id}: {url}"


def reject_many(verdicts: list[curation.Verdict]) -> str:
    """Turn down many candidates at once: each of `verdicts` is `{url, score,
    reason}`, the same fields `reject` takes.

    Each is settled on its own, so one URL that is not pending costs that line
    and not the batch. Returns one line per verdict, in order, saying whether
    it was rejected or why not.
    """
    _require_write()
    with _curation_session() as session:
        return "\n".join(curation.reject_many(session, verdicts))


def reject(url: str, score: int, reason: str) -> str:
    """Turn a candidate down, keeping the score and the reason for it.

    The row stays in the ledger so the URL is never judged twice, and so the
    verdicts can be read back as labels. Write `reason` for a human reading a
    hundred of them later, not for a log line.
    """
    _require_write()
    with _curation_session() as session:
        try:
            curation.reject(session, url, score, reason)
        except curation.CandidateError as exc:
            raise ToolError(str(exc))
    return f"Rejected [{score}/100] {url}"
