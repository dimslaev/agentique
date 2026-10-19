"""First-party analytics: the public ingest endpoint and the admin-only report."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.entry.api.deps import (
    CurrentUserOptional,
    SessionDep,
    get_current_active_superuser,
)
from app.features.analytics.model import AnalyticsEventCreate, AnalyticsReport
from app.features.analytics.service import build_report, record_event

router = APIRouter(prefix="/analytics", tags=["analytics"])


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
    record_event(
        session,
        payload,
        user_id=current_user.id if current_user else None,
        user_agent=request.headers.get("user-agent"),
    )


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
