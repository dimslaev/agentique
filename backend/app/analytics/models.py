"""Analytics schema: first-party pageview and custom-event rows, keyed on an anonymous visitor."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel

from app.platform.dates import get_datetime_utc


class AnalyticsEvent(SQLModel, table=True):
    """First-party analytics event — one row per pageview or custom event.

    No dashboard by design: query the `analytics_event` table directly with SQL.
    """

    __tablename__ = "analytics_event"
    id: int | None = Field(default=None, primary_key=True)
    event: str = Field(default="pageview", index=True)
    path: str | None = Field(default=None, index=True)
    referrer: str | None = None
    # anonymous client id persisted in the browser (localStorage), not a cookie
    visitor_id: str | None = Field(default=None, index=True)
    # set only when the request carries a valid bearer token
    user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    user_agent: str | None = None
    # arbitrary metadata for custom events
    props: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        index=True,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AnalyticsEventCreate(SQLModel):
    event: str = "pageview"
    path: str | None = None
    referrer: str | None = None
    visitor_id: str | None = None
    props: dict = Field(default_factory=dict)
