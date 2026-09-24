"""Pipeline schema: the run record and the reject ledger the funnel writes."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, DateTime, String
from sqlmodel import Field, SQLModel

from app.platform.dates import get_datetime_utc


class RejectStage(StrEnum):
    """The step that turned a URL down, or ``pending`` for one still waiting.

    ``pending`` is the one stage that is not a rejection. The nightly run ends
    by writing it, and the curation agent turns it into an Article or into
    ``below_threshold``. It lives in this table because the row already holds
    everything a judge needs -- title, source, publisher, content, traction --
    and because ``filter_known_urls`` reads the table, so a candidate waiting
    for the agent is not fetched again the next night.
    """

    pending = "pending"
    thin_repo = "thin_repo"
    prefilter = "prefilter"
    duplicate = "duplicate"
    below_threshold = "below_threshold"
    unusable_summary = "unusable_summary"


class Reject(SQLModel, table=True):
    """A URL the funnel turned down, or one waiting on the curation agent.

    The name is the common case. A ``pending`` row is the exception: the same
    columns, holding a candidate the agent has not read yet.

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
    # The judge's one-sentence account of the score; below_threshold only.
    reason: str | None = None
    # Stage-specific evidence: {"stars": 12}, {"keep_proba": 0.08},
    # {"dup_of": "<url>"}.
    # none_as_null: without it an absent detail is stored as JSON 'null', which
    # `detail IS NULL` does not match.
    detail: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True), nullable=True)
    )
    # The repo / model / paper / docs links the article body makes,
    # {"repo": [...], "paper": [...]}; see ``fetching.page_facts``.
    links: dict[str, list[str]] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True), nullable=True)
    )


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
    sources: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    # The table also has a `publishers` column, per-publisher counts from before
    # the Publisher row kept its own (last_fetched_at, last_new_at, last_error).
    # No longer written; its default fills it.
