"""The tables, one module each. The engine is in `engine`, imported on its own.

This package imports every table module, so `SQLModel.metadata` is complete as
soon as anything in `app.core.db` is imported. Alembic's autogenerate reads that
metadata, and a table it cannot see gets no migration.
"""

from __future__ import annotations

from app.core.db import (
    article,
    event,
    ledger,
    like,
    publisher,
    run,
    story,
    subscriber,
    tag,
    user,
)

__all__ = [
    "article",
    "event",
    "ledger",
    "like",
    "publisher",
    "run",
    "story",
    "subscriber",
    "tag",
    "user",
]
