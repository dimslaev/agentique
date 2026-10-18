"""The reject ledger: URLs the funnel turned down, and candidates waiting on the curation agent.

Two jobs. ``filter_known_urls`` reads it so a rejected URL is never fetched and
judged again. And it keeps the evidence - the text the judge saw, the links, the
score, the judge's reason - so a reject can be audited, re-judged under a new
rubric, or used as a training negative instead of vanishing.

The embedding is deliberately not stored: it is a pure function of the stored
title and ``content[:SNIPPET_CAP]``, so it can be rebuilt offline in seconds.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import NotRequired, TypedDict

from sqlalchemy import JSON, Column, DateTime, String, Text
from sqlmodel import Field, Session, SQLModel

from app.core.dates import get_datetime_utc, parse_date

# What a settled reject keeps: enough to re-score with a longer input or
# re-embed with a better model later; the full body would make the ledger most
# of the database.
CONTENT_CAP = 2000
# What a pending candidate keeps, so the curation agent reads the article from
# the db instead of fetching the page again. Trimmed to `CONTENT_CAP` once the
# agent rejects it (`curation.reject`), so only the night's queue is ever this
# large.
CANDIDATE_CAP = 12000


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
    url: str = Field(primary_key=True, sa_type=Text)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
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
    # {"repo": [...], "paper": [...]}; see ``app.core.extract``.
    links: dict[str, list[str]] | None = Field(
        default=None, sa_column=Column(JSON(none_as_null=True), nullable=True)
    )


class LedgerItem(TypedDict):
    """What `record_reject` reads from an item. The pipeline's ``Candidate``
    has these keys and more."""

    title: str
    url: str
    content: str
    published_date: str | None
    source: str
    publisher_id: int
    traction: NotRequired[str]
    links: NotRequired[dict[str, list[str]]]


def _pg_text(text: str) -> str:
    # Postgres text columns reject NUL bytes, and fetched pages occasionally
    # carry one. The failed commit would take the whole source down with it.
    return text.replace("\x00", "")


def record_reject(
    session: Session,
    a: LedgerItem,
    stage: RejectStage,
    *,
    score: int | None = None,
    reason: str | None = None,
    detail: dict[str, object] | None = None,
) -> None:
    """Stage a reject row. The caller commits, as it did for the bare URL."""
    cap = CANDIDATE_CAP if stage == RejectStage.pending else CONTENT_CAP
    content = _pg_text(a["content"][:cap])
    session.merge(
        Reject(
            url=a["url"],
            stage=stage,
            title=_pg_text(a["title"]),
            source=a["source"],
            publisher_id=a["publisher_id"],
            published_at=parse_date(a["published_date"]),
            content=content or None,
            traction=a.get("traction"),
            links=a.get("links") or None,
            score=score,
            reason=reason,
            detail=detail,
        )
    )
