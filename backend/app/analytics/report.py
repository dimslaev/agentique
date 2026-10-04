"""The admin analytics report: who visited, what they opened, where they came from.

Counts outside readers only. A device a superuser has ever signed in on is the
admin's own traffic and is left out everywhere, signed in or not, and so is any
user agent that reads as a crawler or a script. Both are reported as one number
each so the exclusion stays visible.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import CTE, ColumnElement, String, case, cast, distinct, func, or_, true
from sqlmodel import Session, col, select

from app.analytics.models import (
    AnalyticsEvent,
    AnalyticsReport,
    ReportArticle,
    ReportDay,
    ReportRow,
    ReportTotals,
)
from app.audience.models import User
from app.catalog.models import Article
from app.platform.dates import get_datetime_utc

# Loose on purpose: a human caught here costs one visitor, a bot let through
# inflates every number.
BOT_AGENT = r"bot|crawl|spider|slurp|headless|python|curl|wget|preview|lighthouse"
MOBILE_AGENT = r"iphone|ipad|android|mobile"
TOP = 10


def build_report(session: Session, days: int | None) -> AnalyticsReport:
    """The report for the last `days` calendar days in UTC, today included; all time when None."""
    today = get_datetime_utc().date()
    since = (
        datetime.combine(today - timedelta(days=days - 1), time.min, UTC)
        if days
        else None
    )

    admin_ids = select(User.id).where(col(User.is_superuser))
    admin_visitors = select(AnalyticsEvent.visitor_id).where(
        col(AnalyticsEvent.user_id).in_(admin_ids),
        col(AnalyticsEvent.visitor_id).is_not(None),
    )
    agent = col(AnalyticsEvent.user_agent)
    # CASE, not NOT IN: a NULL visitor_id would make NOT IN drop the row.
    audience = case(
        (
            or_(
                col(AnalyticsEvent.user_id).in_(admin_ids),
                col(AnalyticsEvent.visitor_id).in_(admin_visitors),
            ),
            "admin",
        ),
        (or_(agent.is_(None), agent.regexp_match(BOT_AGENT, flags="i")), "bot"),
        else_="human",
    )
    in_window = col(AnalyticsEvent.created_at) >= since if since is not None else true()
    human = (
        select(
            AnalyticsEvent,
            func.date(func.timezone("UTC", AnalyticsEvent.created_at)).label("day"),
        )
        .where(in_window, audience == "human")
        .cte("human")
    )
    h = human.c
    is_pageview = h.event == "pageview"

    visitors, pageviews, article_clicks = session.exec(
        select(
            func.count(distinct(h.visitor_id)),
            func.count().filter(is_pageview),
            func.count().filter(h.event == "article_click"),
        ).select_from(human)
    ).one()

    returning_visitors = (
        select(h.visitor_id)
        .where(h.visitor_id.is_not(None))
        .group_by(h.visitor_id)
        .having(func.count(distinct(h.day)) > 1)
        .subquery()
    )
    excluded = dict(
        session.exec(
            select(audience, func.count())
            .where(in_window, AnalyticsEvent.event == "pageview", audience != "human")
            .group_by(audience)
        ).all()
    )
    totals = ReportTotals(
        visitors=visitors,
        pageviews=pageviews,
        returning_visitors=session.exec(
            select(func.count()).select_from(returning_visitors)
        ).one(),
        article_clicks=article_clicks,
        admin_pageviews=excluded.get("admin", 0),
        bot_pageviews=excluded.get("bot", 0),
    )

    by_day = {
        day: (v, pv)
        for day, v, pv in session.exec(
            select(
                h.day,
                func.count(distinct(h.visitor_id)),
                func.count().filter(is_pageview),
            ).group_by(h.day)
        ).all()
    }
    first_day = since.date() if since else min(by_day, default=today)
    daily = []
    for day in _days(first_day, today):
        day_visitors, day_pageviews = by_day.get(day, (0, 0))
        daily.append(ReportDay(day=day, visitors=day_visitors, pageviews=day_pageviews))

    referrer_host = func.coalesce(
        func.substring(h.referrer, r"^https?://([^/]+)"), h.referrer
    )
    device = case(
        (h.user_agent.regexp_match(MOBILE_AGENT, flags="i"), "mobile"), else_="desktop"
    )

    return AnalyticsReport(
        days=days,
        totals=totals,
        daily=daily,
        pages=_ranked(session, human, h.path, is_pageview & h.path.is_not(None)),
        referrers=_ranked(
            session, human, referrer_host, is_pageview & h.referrer.is_not(None)
        ),
        events=_ranked(session, human, h.event, ~is_pageview),
        articles=_articles(session, human),
        devices=_ranked(session, human, device, is_pageview),
    )


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def _ranked(
    session: Session,
    human: CTE,
    label: ColumnElement[str],
    where: ColumnElement[bool],
) -> list[ReportRow]:
    """Rows grouped by `label`, most frequent first, each with its event count and distinct visitors."""
    count = func.count()
    rows = session.exec(
        select(label, count, func.count(distinct(human.c.visitor_id)))
        .select_from(human)
        .where(where)
        .group_by(label)
        .order_by(count.desc(), label)
        .limit(TOP)
    ).all()
    return [ReportRow(label=lb, count=c, visitors=v) for lb, c, v in rows]


def _articles(session: Session, human: CTE) -> list[ReportArticle]:
    """The most clicked articles. Joined as text so a malformed id from the client can't fail the cast."""
    h = human.c
    article_id = h.props["article_id"].as_string()
    clicks = func.count()
    rows = session.exec(
        select(article_id, Article.title, clicks, func.count(distinct(h.visitor_id)))
        .select_from(human)
        .outerjoin(Article, cast(col(Article.id), String) == article_id)
        .where(h.event == "article_click", article_id.is_not(None))
        .group_by(article_id, col(Article.title))
        .order_by(clicks.desc(), article_id)
        .limit(TOP)
    ).all()
    return [
        ReportArticle(article_id=a, title=t, clicks=c, visitors=v)
        for a, t, c, v in rows
    ]
