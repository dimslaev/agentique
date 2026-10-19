"""One row per nightly pipeline run."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.core.dates import get_datetime_utc


class PipelineRun(SQLModel, table=True):
    """One row per nightly pipeline run: did it finish, how long it took, and
    what each source fetched and queued."""

    __tablename__ = "pipeline_run"
    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    duration_ms: int | None = None
    ok: bool = Field(default=False)
    # [{source, fetched, queued, error}]. Rows from before 2026-09-23 carry
    # the older, longer funnel shape.
    sources: list[dict[str, object]] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False)
    )
    # Per-publisher counts from before the Publisher row kept its own
    # (last_fetched_at, last_new_at, last_error). No longer read; new rows get
    # an empty list.
    publishers: list[dict[str, object]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    )
