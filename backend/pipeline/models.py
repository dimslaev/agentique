"""Pipeline schema: the run record and the scored-url ledger the funnel writes."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel

from app.platform.dates import get_datetime_utc


class ScoredUrl(SQLModel, table=True):
    __tablename__ = "scored_url"
    url: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PipelineRun(SQLModel, table=True):
    """One row per nightly pipeline run — the numeric record the verifier reasons over."""

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
    # per-source funnel counts: [{source, fetched, filtered_known, ..., inserted, errors}]
    sources: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    # per-publisher fetch/insert counts within the "Feeds" source: [{name, fetched, inserted, error}]
    publishers: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
