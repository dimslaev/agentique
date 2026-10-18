"""The engine, the request session, and the tables against the migrated schema."""

from __future__ import annotations

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlmodel import SQLModel

from app.core import db
from app.core.db.engine import engine, get_session
from app.core.settings import settings
from app.entry.api.deps import SessionDep
from app.features.collect import service as collect
from app.main import app  # noqa: F401  # every module that could declare a table


def test_every_table_lives_in_core_db():
    """The app is fully imported here, so a table declared anywhere else shows
    up in the metadata and not in `app.core.db`."""
    declared = set()
    for name in db.__all__:
        for cls in vars(getattr(db, name)).values():
            if isinstance(cls, type) and issubclass(cls, SQLModel):
                table = getattr(cls, "__table__", None)
                if table is not None:
                    declared.add(table.name)
    assert declared == set(SQLModel.metadata.tables)


def test_tables_match_the_migrations():
    """`alembic check` in the test run: a table edit without a migration, or a
    migration the tables do not declare, fails here."""
    with engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(context, SQLModel.metadata)
    assert diff == []


def test_engine_connects_with_the_settings_credentials():
    assert engine.url.database == settings.POSTGRES_DB
    with engine.connect() as conn:
        user = conn.execute(text("SELECT current_user")).scalar_one()
    assert user == settings.POSTGRES_USER


def test_the_request_session_is_closed_after_the_request():
    sessions = get_session()
    session = next(sessions)
    assert session.bind is engine
    session.execute(text("SELECT 1"))
    assert session.in_transaction()
    sessions.close()
    assert not session.in_transaction()


def test_routes_and_the_collect_run_share_the_engine():
    assert collect.engine is engine
    assert SessionDep.__metadata__[0].dependency is get_session
