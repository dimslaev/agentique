"""Analytics shapes: the event a page posts, and the admin report."""

from __future__ import annotations

from datetime import date

from sqlmodel import Field, SQLModel


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
    # registered readers, superusers left out: all time, and new inside the window
    users: int
    signups: int
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
