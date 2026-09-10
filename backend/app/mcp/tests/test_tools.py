"""The MCP tools: the read-only guard, the row cap, JSON coercion, and the two wrappers."""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest
from fastmcp.exceptions import ToolError
from sqlalchemy import Engine
from sqlmodel import create_engine

from app.mcp import tools
from app.platform.settings import settings


@pytest.fixture(scope="module")
def ro_engine() -> Generator[Engine]:
    """`tools.engine` built on the test credentials instead of `agentique_ro`.

    The role does not exist outside the production box, but the DSN it is
    reached through is the same one settings build, read-only options and all,
    so the guard under test is the real one.
    """
    dsn = settings.model_copy(
        update={
            "MCP_DB_USER": settings.POSTGRES_USER,
            "MCP_DB_PASSWORD": settings.POSTGRES_PASSWORD,
        }
    ).MCP_DATABASE_URI
    engine = create_engine(dsn)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _use_ro_engine(ro_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "engine", ro_engine)


def test_select_returns_columns_and_rows():
    result = json.loads(tools.sql_query("SELECT 1 AS n, 'a' AS label"))
    assert result == {
        "columns": ["n", "label"],
        "rows": [{"n": 1, "label": "a"}],
        "truncated": False,
    }


def test_rows_are_capped_and_flagged():
    result = json.loads(
        tools.sql_query(f"SELECT i FROM generate_series(1, {tools.MAX_ROWS + 5}) AS i")
    )
    assert len(result["rows"]) == tools.MAX_ROWS
    assert result["truncated"] is True


def test_a_result_that_exactly_fills_the_cap_is_not_truncated():
    result = json.loads(
        tools.sql_query(f"SELECT i FROM generate_series(1, {tools.MAX_ROWS}) AS i")
    )
    assert len(result["rows"]) == tools.MAX_ROWS
    assert result["truncated"] is False


def test_timestamps_and_numerics_survive_serialisation():
    result = json.loads(
        tools.sql_query(
            "SELECT TIMESTAMP '2026-01-02 03:04:05' AS ts, 1.5::numeric AS amount"
        )
    )
    assert result["rows"] == [{"ts": "2026-01-02T03:04:05", "amount": "1.5"}]


def test_a_write_is_rejected_by_the_read_only_transaction():
    # Not a syntax check on the way in: Postgres refuses it, so anything the
    # tool failed to anticipate is refused too.
    with pytest.raises(ToolError, match="read-only transaction"):
        tools.sql_query("UPDATE article SET title = title WHERE false")


def test_anything_postgres_cannot_plan_as_a_query_is_refused():
    # Planning is the filter: COPY, SET, DO and a second statement after a
    # semicolon never reach execution.
    with pytest.raises(ToolError):
        tools.sql_query("SET application_name = 'mcp'")


def test_the_user_table_is_not_readable():
    with pytest.raises(ToolError, match="Not readable through this tool: user"):
        tools.sql_query('SELECT email FROM "user"')


def test_the_user_table_is_not_readable_through_a_subquery():
    # The check walks the whole plan, so hiding it below the top node does not
    # help -- nor would a join, a CTE or a view.
    with pytest.raises(ToolError, match="Not readable through this tool: user"):
        tools.sql_query('SELECT 1 WHERE EXISTS (SELECT 1 FROM "user")')


def test_a_second_statement_after_a_semicolon_cannot_smuggle_a_read():
    with pytest.raises(ToolError):
        tools.sql_query('SELECT 1; SELECT email FROM "user"')


def test_a_statement_crafted_to_close_the_explain_prefix_is_still_one_statement():
    # The prefix is text, so this would be three valid statements if anything
    # but a prepared statement ran it -- and the middle one is the read.
    with pytest.raises(ToolError):
        tools.sql_query(
            'SELECT 1) AS x; SELECT email FROM "user"; SELECT * FROM (SELECT 1'
        )


def test_web_fetch_returns_extracted_text(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        tools, "fetch_and_extract", lambda url, max_length: f"text of {url}"
    )
    assert (
        tools.web_fetch("https://example.com/post")
        == "text of https://example.com/post"
    )


def test_web_fetch_passes_the_length_cap_through(monkeypatch: pytest.MonkeyPatch):
    seen: list[tuple[str, int]] = []

    def fake(url: str, max_length: int) -> str:
        seen.append((url, max_length))
        return "text"

    monkeypatch.setattr(tools, "fetch_and_extract", fake)
    tools.web_fetch("https://example.com/post", max_length=50)
    assert seen == [("https://example.com/post", 50)]


def test_web_fetch_fails_loudly_when_nothing_is_readable(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(tools, "fetch_and_extract", lambda url, max_length: "")
    with pytest.raises(ToolError, match="No readable content"):
        tools.web_fetch("https://example.com/paywalled")


def test_web_search_forwards_every_argument(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, int, list[str] | None]] = []

    def fake(
        query: str, max_results: int, include_domains: list[str] | None
    ) -> list[dict[str, str | None]]:
        calls.append((query, max_results, include_domains))
        return [{"title": "t", "url": "u", "description": "d", "published_date": None}]

    monkeypatch.setattr(tools, "tavily_search", fake)
    results = tools.web_search("gpt-5", max_results=3, include_domains=["openai.com"])
    assert calls == [("gpt-5", 3, ["openai.com"])]
    assert results[0]["url"] == "u"
