"""Pipeline schema: the run record and the reject ledger the funnel writes."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, DateTime, String
from sqlmodel import Field, SQLModel

from app.platform.dates import get_datetime_utc


class RejectStage(StrEnum):
    """The step that turned a URL down."""

    thin_repo = "thin_repo"
    prefilter = "prefilter"
    duplicate = "duplicate"
    below_threshold = "below_threshold"
    unusable_summary = "unusable_summary"


class Reject(SQLModel, table=True):
    """A URL the funnel turned down: what it saw, and why it said no.

    Every column but ``url`` and ``created_at`` is nullable: rows written before
    the ledger kept evidence carry only the URL.
    """

    # Still named scored_url: deploy runs additive migrations only, and a
    # rename is not one.
    __tablename__ = "scored_url"
    url: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)
    # A plain string, not a Postgres enum, so a new stage needs no migration.
    stage: RejectStage | None = Field(default=None, sa_type=String)
    title: str | None = None
    source: str | None = None
    publisher_id: int | None = Field(default=None, foreign_key="publisher.id")
    published_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    content: str | None = None
    traction: str | None = None
    score: int | None = None
    # The scorer's one-sentence account of the score; below_threshold only.
    reason: str | None = None
    # Stage-specific evidence: {"stars": 12}, {"keep_proba": 0.08},
    # {"dup_of": "<url>"}.
    detail: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )


class PipelineRun(SQLModel, table=True):
    """One row per nightly pipeline run — what it inserted, and the counts behind it."""

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
    # per-source funnel counts plus what landed:
    # [{source, fetched, filtered_known, ..., inserted, articles, errors}]
    sources: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    # per-publisher fetch/insert counts within the "Feeds" source: [{name, fetched, inserted, error}]
    publishers: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
