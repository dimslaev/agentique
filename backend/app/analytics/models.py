"""Analytics schema: first-party pageview and custom-event rows, keyed on an anonymous visitor, and the admin report built from them."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel

from app.platform.dates import get_datetime_utc


class AnalyticsEvent(SQLModel, table=True):
    """First-party analytics event — one row per pageview or custom event."""

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


# ─── Admin report ────────────────────────────────────────────────────────────


class ReportTotals(SQLModel):
    visitors: int
    pageviews: int
    # seen on more than one day inside the window
    returning_visitors: int
    article_clicks: int
    # left out of every other number in the report
    admin_pageviews: int
    bot_pageviews: int


class ReportDay(SQLModel):
    day: date
    visitors: int
    pageviews: int


class ReportRow(SQLModel):
    label: str
    count: int
    visitors: int


class ReportArticle(SQLModel):
    article_id: str
    # None when the article has since been deleted
    title: str | None
    clicks: int
    visitors: int


class AnalyticsReport(SQLModel):
    # None means all time
    days: int | None
    totals: ReportTotals
    daily: list[ReportDay]
    pages: list[ReportRow]
    referrers: list[ReportRow]
    events: list[ReportRow]
    articles: list[ReportArticle]
    devices: list[ReportRow]
