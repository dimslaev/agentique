"""The engine, the request session, and the tables against the migrated schema."""

from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlmodel import SQLModel

from app.core.db.engine import engine, get_session
from app.core.settings import settings


def test_tables_match_the_migrations() -> None:
    """`alembic check` in the test run: a table edit without a migration, or a
    migration the tables do not declare, fails here."""
    with engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(context, SQLModel.metadata)
    assert diff == []


def test_engine_connects_with_the_settings_credentials() -> None:
    assert engine.url.database == settings.POSTGRES_DB
    with engine.connect() as conn:
        user = conn.execute(text("SELECT current_user")).scalar_one()
    assert user == settings.POSTGRES_USER


def test_the_request_session_is_closed_after_the_request() -> None:
    sessions = get_session()
    session = next(sessions)
    assert session.bind is engine
    session.connection().execute(text("SELECT 1"))
    assert session.in_transaction()
    sessions.close()
    assert not session.in_transaction()
