"""Database engine for the pipeline.

The engine is built lazily so importing pipeline modules — in tests, or to
poke at a pure function — does not require a database.
"""

from __future__ import annotations

from sqlalchemy import Engine
from sqlmodel import create_engine

from pipeline.config import postgres_url

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(postgres_url())
    return _engine
