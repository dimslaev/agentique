"""Database engine for the pipeline.

The engine is built lazily so importing pipeline modules — in tests, or to
poke at a pure function — does not require a database.
"""

from __future__ import annotations

import os
from urllib.parse import quote

from sqlalchemy import Engine
from sqlmodel import create_engine

_engine: Engine | None = None


def postgres_url() -> str:
    """Read straight from os.environ rather than app.core.config.settings: the
    pipeline stays decoupled from the backend's full Settings object."""
    server = os.environ["POSTGRES_SERVER"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = quote(os.environ["POSTGRES_USER"], safe="")
    password = quote(os.environ.get("POSTGRES_PASSWORD", ""), safe="")
    db = os.environ.get("POSTGRES_DB", "")
    return f"postgresql+psycopg://{user}:{password}@{server}:{port}/{db}"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(postgres_url())
    return _engine
