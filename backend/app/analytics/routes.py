"""First-party analytics: the public ingest endpoint and the admin-only report."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query, Request

from app.analytics.models import AnalyticsEvent, AnalyticsEventCreate, AnalyticsReport
from app.analytics.report import build_report
from app.deps import CurrentUserOptional, SessionDep, get_current_active_superuser

router = APIRouter(prefix="/analytics", tags=["analytics"])

# cap oversized strings so a bad/malicious client can't bloat the table
_MAX_LEN = 2048


def _truncate(value: str | None) -> str | None:
    return value[:_MAX_LEN] if value else None


def _without_query(value: str | None) -> str | None:
    # A sign-in link carries its token in the query string, and nothing reads
    # the query back, so none is kept.
    return re.split(r"[?#]", value, maxsplit=1)[0] if value else None


@router.post("/collect", status_code=204)
def collect_event(
    session: SessionDep,
    current_user: CurrentUserOptional,
    payload: AnalyticsEventCreate,
    request: Request,
) -> None:
    """Record one analytics event. Public and fire-and-forget (returns 204).

    Attaches the user id when the request carries a valid bearer token;
    otherwise the event is anonymous.
    """
    event = AnalyticsEvent(
        event=_truncate(payload.event) or "pageview",
        path=_truncate(_without_query(payload.path)),
        # Only the client's `document.referrer` is meaningful. The request's own
        # Referer header is always our site, so a fallback to it would file every
        # direct visit under agentique.ch.
        referrer=_truncate(_without_query(payload.referrer)),
        visitor_id=_truncate(payload.visitor_id),
        user_id=current_user.id if current_user else None,
        user_agent=_truncate(request.headers.get("user-agent")),
        props=payload.props,
    )
    session.add(event)
    session.commit()


@router.get(
    "/report",
    response_model=AnalyticsReport,
    dependencies=[Depends(get_current_active_superuser)],
)
def read_report(
    session: SessionDep,
    days: int | None = Query(default=None, ge=1, le=3650),
) -> AnalyticsReport:
    """Superusers only. Outside readers over the last `days` days, all time when omitted."""
    return build_report(session, days)
