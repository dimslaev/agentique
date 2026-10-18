"""The database DSNs settings build, for credentials with URL-reserved characters."""

from __future__ import annotations

import psycopg
from sqlalchemy.engine import make_url

from app.core.settings import settings

PASSWORD = "p@ss/w:rd#% x"


def test_engine_dsn_keeps_reserved_characters_in_the_password():
    copy = settings.model_copy(
        update={"POSTGRES_USER": "me@host", "POSTGRES_PASSWORD": PASSWORD}
    )
    url = make_url(str(copy.SQLALCHEMY_DATABASE_URI))
    assert (url.username, url.password) == ("me@host", PASSWORD)
    assert (url.host, url.database) == (settings.POSTGRES_SERVER, settings.POSTGRES_DB)


def test_mcp_dsn_keeps_reserved_characters_in_the_password():
    copy = settings.model_copy(update={"MCP_DB_PASSWORD": PASSWORD})
    params = psycopg.conninfo.conninfo_to_dict(copy.MCP_DATABASE_URI)
    assert (params["user"], params["password"]) == (settings.MCP_DB_USER, PASSWORD)
    assert "default_transaction_read_only=on" in str(params["options"])


def test_mcp_dsn_without_a_password_has_none():
    copy = settings.model_copy(update={"MCP_DB_PASSWORD": ""})
    params = psycopg.conninfo.conninfo_to_dict(copy.MCP_DATABASE_URI)
    assert "password" not in params
