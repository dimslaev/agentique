"""`sql_query`: the read-only guard, the blocked tables, the row cap, and JSON coercion."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken
from sqlalchemy import text
from sqlmodel import Session

from app.core.db.engine import engine
from app.core.db.factories import create_random_article
from app.core.settings import settings
from app.entry.mcp import sql_query as tool
from app.entry.mcp.auth import USER_SCOPE


@pytest.fixture(autouse=True)
def _test_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the tool at the test credentials instead of `agentique_ro`.

    The role does not exist outside the production box, but the DSN is the one
    settings build, read-only options and all, so the guard under test is real.
    """
    monkeypatch.setattr(
        tool,
        "DSN",
        settings.model_copy(
            update={
                "MCP_DB_USER": settings.POSTGRES_USER,
                "MCP_DB_PASSWORD": settings.POSTGRES_PASSWORD,
            }
        ).MCP_DATABASE_URI,
    )


def test_select_returns_columns_and_rows() -> None:
    result = json.loads(tool.sql_query("SELECT 1 AS n, 'a' AS label"))
    assert result == {
        "columns": ["n", "label"],
        "rows": [{"n": 1, "label": "a"}],
        "truncated": False,
    }


def test_rows_are_capped_and_flagged() -> None:
    result = json.loads(
        tool.sql_query(f"SELECT i FROM generate_series(1, {tool.MAX_ROWS + 5}) AS i")
    )
    assert len(result["rows"]) == tool.MAX_ROWS
    assert result["truncated"] is True


def test_a_result_that_exactly_fills_the_cap_is_not_truncated() -> None:
    result = json.loads(
        tool.sql_query(f"SELECT i FROM generate_series(1, {tool.MAX_ROWS}) AS i")
    )
    assert len(result["rows"]) == tool.MAX_ROWS
    assert result["truncated"] is False


def test_timestamps_and_numerics_survive_serialisation() -> None:
    result = json.loads(
        tool.sql_query(
            "SELECT TIMESTAMP '2026-01-02 03:04:05' AS ts, 1.5::numeric AS amount"
        )
    )
    assert result["rows"] == [{"ts": "2026-01-02T03:04:05", "amount": "1.5"}]


def test_a_write_is_rejected_by_the_read_only_transaction() -> None:
    # Not a syntax check on the way in: Postgres refuses it, so anything the
    # tool failed to anticipate is refused too.
    with pytest.raises(ToolError, match="read-only transaction"):
        tool.sql_query("UPDATE article SET title = title WHERE false")


def test_anything_postgres_cannot_plan_as_a_query_is_refused() -> None:
    # Planning is the filter: COPY, SET, DO and a second statement after a
    # semicolon never reach execution.
    with pytest.raises(ToolError):
        tool.sql_query("SET application_name = 'mcp'")


def test_the_user_table_is_not_readable() -> None:
    with pytest.raises(ToolError, match="Not readable through this tool: user"):
        tool.sql_query('SELECT email FROM "user"')


def test_the_user_table_is_not_readable_through_a_subquery() -> None:
    # The check walks the whole plan, so hiding it below the top node does not
    # help -- nor would a join, a CTE or a view.
    with pytest.raises(ToolError, match="Not readable through this tool: user"):
        tool.sql_query('SELECT 1 WHERE EXISTS (SELECT 1 FROM "user")')


def test_a_second_statement_after_a_semicolon_cannot_smuggle_a_read() -> None:
    with pytest.raises(ToolError):
        tool.sql_query('SELECT 1; SELECT email FROM "user"')


def test_a_statement_crafted_to_close_the_explain_prefix_is_still_one_statement() -> (
    None
):
    # The prefix is text, so this would be three valid statements if anything
    # but a prepared statement ran it -- and the middle one is the read.
    with pytest.raises(ToolError):
        tool.sql_query(
            'SELECT 1) AS x; SELECT email FROM "user"; SELECT * FROM (SELECT 1'
        )


# ─── Under a reader's own token ──────────────────────────────────────────────


@pytest.fixture
def reader(monkeypatch: pytest.MonkeyPatch, reader_sql: None) -> None:  # noqa: ARG001
    """Answer the tool's scope check as a caller holding a personal token."""
    monkeypatch.setattr(
        tool,
        "get_access_token",
        lambda: AccessToken(token="t", client_id="c", scopes=[USER_SCOPE]),
    )


# Read from the database, so a table added later is covered.
with engine.connect() as _conn:
    TABLES = sorted(
        _conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        ).scalars()
    )


def test_there_are_tables_to_refuse() -> None:
    assert {"article", "user", "scored_url", "article_like", "mcp_token"} <= set(TABLES)


@pytest.mark.usefixtures("reader", "made")
def test_a_reader_joins_the_public_views(
    db: Session, made: dict[str, list[int]]
) -> None:
    article = create_random_article(db)
    assert article.id is not None
    made["articles"].append(article.id)
    made["publishers"].append(article.publisher_id)

    result = json.loads(
        tool.sql_query(
            "SELECT a.title, a.kind, a.like_count, p.slug FROM article a "
            f"JOIN publisher p ON p.id = a.publisher_id WHERE a.id = {article.id}"
        )
    )

    assert result["columns"] == ["title", "kind", "like_count", "slug"]
    assert result["rows"][0]["title"] == article.title
    assert result["rows"][0]["kind"] == "post"
    assert result["rows"][0]["like_count"] == 0


@pytest.mark.usefixtures("reader")
def test_the_public_views_hold_only_the_public_columns() -> None:
    result = json.loads(
        tool.sql_query(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public_api' ORDER BY 1, ordinal_position"
        )
    )
    columns: dict[str, list[str]] = {}
    for row in result["rows"]:
        columns.setdefault(row["table_name"], []).append(row["column_name"])

    assert columns == {
        "article": [
            "id",
            "title",
            "url",
            "publisher_id",
            "published_at",
            "score",
            "kind",
            "summary",
            "like_count",
        ],
        "article_tag": ["article_id", "tag_id"],
        "publisher": ["id", "slug", "name", "kind"],
        "tag": ["id", "slug", "name"],
    }


@pytest.mark.usefixtures("reader")
@pytest.mark.parametrize("column", ["content", "score_reason", "embedding"])
def test_a_reader_cannot_select_an_internal_article_column(column: str) -> None:
    with pytest.raises(ToolError, match="does not exist"):
        tool.sql_query(f"SELECT {column} FROM article")
    with pytest.raises(ToolError, match="permission denied"):
        tool.sql_query(f"SELECT {column} FROM public.article")


@pytest.mark.usefixtures("reader")
@pytest.mark.parametrize("table", TABLES)
def test_a_reader_cannot_read_any_table(table: str) -> None:
    with pytest.raises(ToolError, match="permission denied"):
        tool.sql_query(f'SELECT 1 FROM public."{table}" LIMIT 1')


@pytest.fixture
def no_usage_on_public() -> Iterator[None]:
    """The box's grants: no role but the owner may look inside `public`."""
    with engine.begin() as conn:
        conn.execute(text("REVOKE USAGE ON SCHEMA public FROM PUBLIC"))
    yield
    with engine.begin() as conn:
        conn.execute(text("GRANT USAGE ON SCHEMA public TO PUBLIC"))


@pytest.mark.usefixtures("reader", "no_usage_on_public")
def test_a_reader_reads_the_views_without_usage_on_public() -> None:
    result = json.loads(tool.sql_query("SELECT count(*) AS n FROM article"))
    assert result["columns"] == ["n"]
    with pytest.raises(ToolError, match="permission denied for schema public"):
        tool.sql_query("SELECT 1 FROM public.article")


@pytest.mark.usefixtures("reader")
def test_a_reader_cannot_write() -> None:
    with pytest.raises(ToolError):
        tool.sql_query("DELETE FROM article")


@pytest.mark.usefixtures("reader")
def test_a_reader_cannot_lift_the_three_second_timeout() -> None:
    with pytest.raises(ToolError, match="statement timeout"):
        tool.sql_query(
            "SELECT set_config('statement_timeout', '0', false), pg_sleep(5)"
        )


def test_a_reader_is_refused_when_the_public_role_can_read_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_test_dsn` logs in as the superuser, standing in for a deploy that set
    `MCP_PUBLIC_DB_USER` to a role with grants on the tables."""
    monkeypatch.setattr(tool, "PUBLIC_DSN", tool.DSN)
    monkeypatch.setattr(
        tool,
        "get_access_token",
        lambda: AccessToken(token="t", client_id="c", scopes=[USER_SCOPE]),
    )
    with pytest.raises(ToolError, match="not set up for personal tokens"):
        tool.sql_query("SELECT 1")


def test_a_shared_token_does_not_use_the_public_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tool, "PUBLIC_DSN", "postgresql://nobody@nowhere.invalid/x")
    monkeypatch.setattr(
        tool,
        "get_access_token",
        lambda: AccessToken(token="t", client_id="c", scopes=[]),
    )
    result = json.loads(tool.sql_query("SELECT count(*) AS n FROM article"))
    assert result["columns"] == ["n"]
