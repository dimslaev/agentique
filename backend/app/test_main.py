"""What only the whole app can show: every table is declared in `app.core.db`,
and the routes and the collect run share one engine."""

from __future__ import annotations

from typing import get_args

from sqlmodel import SQLModel

from app.core import db
from app.core.db.engine import engine, get_session
from app.entry.api.deps import SessionDep
from app.features.collect import service as collect
from app.main import app  # noqa: F401  # every module that could declare a table


def test_every_table_lives_in_core_db() -> None:
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


def test_routes_and_the_collect_run_share_the_engine() -> None:
    assert vars(collect)["engine"] is engine
    assert get_args(SessionDep)[1].dependency is get_session
