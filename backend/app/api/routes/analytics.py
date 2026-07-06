from fastapi import APIRouter, Request

from app.api.deps import SessionDep
from app.api.deps_agentique import CurrentUserOptional
from app.models_agentique import AnalyticsEvent, AnalyticsEventCreate

router = APIRouter(prefix="/analytics", tags=["analytics"])

# cap oversized strings so a bad/malicious client can't bloat the table
_MAX_LEN = 2048


def _truncate(value: str | None) -> str | None:
    return value[:_MAX_LEN] if value else None


@router.post("/collect", status_code=204)
def collect_event(
    session: SessionDep,
    current_user: CurrentUserOptional,
    payload: AnalyticsEventCreate,
    request: Request,
) -> None:
    """Record one analytics event. Public and fire-and-forget (returns 204).

    Attaches the user id when the request carries a valid bearer token;
    otherwise the event is anonymous. No dashboard — query the table in SQL.
    """
    event = AnalyticsEvent(
        event=_truncate(payload.event) or "pageview",
        path=_truncate(payload.path),
        referrer=_truncate(payload.referrer)
        or _truncate(request.headers.get("referer")),
        visitor_id=_truncate(payload.visitor_id),
        user_id=current_user.id if current_user else None,
        user_agent=_truncate(request.headers.get("user-agent")),
        props=payload.props,
    )
    session.add(event)
    session.commit()
