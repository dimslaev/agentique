"""Database engine for the pipeline.

Reads POSTGRES_* from os.environ directly (like the rest of the pipeline) rather
than app.core.config.settings, so the pipeline stays decoupled from the
backend's full Settings object. The engine is built lazily so importing pipeline
modules — in tests, or to poke at a pure function — does not require a database.
"""

from __future__ import annotations

import os

from sqlalchemy import Engine
from sqlmodel import create_engine

_engine: Engine | None = None


def _build_db_url() -> str:
    server = os.environ["POSTGRES_SERVER"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ["POSTGRES_USER"]
    password = os.environ.get("POSTGRES_PASSWORD", "")
    db = os.environ.get("POSTGRES_DB", "")
    return f"postgresql+psycopg://{user}:{password}@{server}:{port}/{db}"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_build_db_url())
    return _engine
