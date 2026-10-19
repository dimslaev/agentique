"""Alembic's entry point: run the migrations against the app's database."""

from __future__ import annotations

import logging

from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

import app.core.db  # noqa: F401  # declares every table on SQLModel.metadata
from app.core.settings import settings

# pyproject.toml's [tool.alembic] has no logging section, so it is set here.
logging.basicConfig(format="%(levelname)-5.5s [%(name)s] %(message)s")
logging.getLogger("alembic").setLevel(logging.INFO)

target_metadata = SQLModel.metadata
url = str(settings.SQLALCHEMY_DATABASE_URI)


def run_migrations_offline() -> None:
    """Emit the SQL to stdout instead of running it."""
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
