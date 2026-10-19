"""What only the whole app can show: every table is declared in `app.core.db`,
the routes and the collect run share one engine, and the API process logs at
INFO."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
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


def test_the_api_process_prints_the_dev_sign_in_link() -> None:
    """A fresh interpreter, because pytest installs its own log handlers. Without
    a logging config the link is dropped and a developer can't sign in."""
    # Empty env vars don't override `.env`, so the send is stubbed out instead:
    # a developer's `.env` may hold a real Resend key.
    script = (
        "import logging\n"
        "import app.main\n"
        "assert logging.getLogger('httpx').getEffectiveLevel() == logging.WARNING\n"
        "from app.features.audience import email\n"
        "email.send_email = lambda **_: None\n"
        "email.send_link_email('dev@example.com', "
        "email.generate_sign_in_email('t0ken'), 't0ken')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        env=os.environ | {"ENVIRONMENT": "development"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "[dev] Sign-in link for dev@example.com" in result.stderr
    assert "token=t0ken" in result.stderr
