"""`sql_query`: the read-only guard, the blocked tables, the row cap, and JSON coercion."""

from __future__ import annotations

import json

import pytest
from fastmcp.exceptions import ToolError

from app.core.settings import settings
from app.entry.mcp import sql_query as tool


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


def test_select_returns_columns_and_rows():
    result = json.loads(tool.sql_query("SELECT 1 AS n, 'a' AS label"))
    assert result == {
        "columns": ["n", "label"],
        "rows": [{"n": 1, "label": "a"}],
        "truncated": False,
    }


def test_rows_are_capped_and_flagged():
    result = json.loads(
        tool.sql_query(f"SELECT i FROM generate_series(1, {tool.MAX_ROWS + 5}) AS i")
    )
    assert len(result["rows"]) == tool.MAX_ROWS
    assert result["truncated"] is True


def test_a_result_that_exactly_fills_the_cap_is_not_truncated():
    result = json.loads(
        tool.sql_query(f"SELECT i FROM generate_series(1, {tool.MAX_ROWS}) AS i")
    )
    assert len(result["rows"]) == tool.MAX_ROWS
    assert result["truncated"] is False


def test_timestamps_and_numerics_survive_serialisation():
    result = json.loads(
        tool.sql_query(
            "SELECT TIMESTAMP '2026-01-02 03:04:05' AS ts, 1.5::numeric AS amount"
        )
    )
    assert result["rows"] == [{"ts": "2026-01-02T03:04:05", "amount": "1.5"}]


def test_a_write_is_rejected_by_the_read_only_transaction():
    # Not a syntax check on the way in: Postgres refuses it, so anything the
    # tool failed to anticipate is refused too.
    with pytest.raises(ToolError, match="read-only transaction"):
        tool.sql_query("UPDATE article SET title = title WHERE false")


def test_anything_postgres_cannot_plan_as_a_query_is_refused():
    # Planning is the filter: COPY, SET, DO and a second statement after a
    # semicolon never reach execution.
    with pytest.raises(ToolError):
        tool.sql_query("SET application_name = 'mcp'")


def test_the_user_table_is_not_readable():
    with pytest.raises(ToolError, match="Not readable through this tool: user"):
        tool.sql_query('SELECT email FROM "user"')


def test_the_user_table_is_not_readable_through_a_subquery():
    # The check walks the whole plan, so hiding it below the top node does not
    # help -- nor would a join, a CTE or a view.
    with pytest.raises(ToolError, match="Not readable through this tool: user"):
        tool.sql_query('SELECT 1 WHERE EXISTS (SELECT 1 FROM "user")')


def test_a_second_statement_after_a_semicolon_cannot_smuggle_a_read():
    with pytest.raises(ToolError):
        tool.sql_query('SELECT 1; SELECT email FROM "user"')


def test_a_statement_crafted_to_close_the_explain_prefix_is_still_one_statement():
    # The prefix is text, so this would be three valid statements if anything
    # but a prepared statement ran it -- and the middle one is the read.
    with pytest.raises(ToolError):
        tool.sql_query(
            'SELECT 1) AS x; SELECT email FROM "user"; SELECT * FROM (SELECT 1'
        )
