from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import AnalyticsEvent, User


def _latest_event(db: Session, visitor_id: str) -> AnalyticsEvent | None:
    return db.exec(
        select(AnalyticsEvent)
        .where(AnalyticsEvent.visitor_id == visitor_id)
        .order_by(col(AnalyticsEvent.id).desc())
    ).first()


def test_collect_anonymous_pageview(client: TestClient, db: Session) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/analytics/collect",
        json={"path": "/articles", "visitor_id": "anon-1"},
    )
    assert r.status_code == 204

    event = _latest_event(db, "anon-1")
    assert event is not None
    assert event.event == "pageview"
    assert event.path == "/articles"
    assert event.user_id is None
    # user agent captured from the request headers
    assert event.user_agent is not None


def test_collect_defaults_event_to_pageview(client: TestClient, db: Session) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/analytics/collect",
        json={"visitor_id": "anon-2"},
    )
    assert r.status_code == 204
    event = _latest_event(db, "anon-2")
    assert event is not None
    assert event.event == "pageview"
    assert event.path is None


def test_collect_custom_event_with_props(client: TestClient, db: Session) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/analytics/collect",
        json={
            "event": "article_liked",
            "path": "/articles/5",
            "visitor_id": "anon-3",
            "props": {"article_id": 5},
        },
    )
    assert r.status_code == 204
    event = _latest_event(db, "anon-3")
    assert event is not None
    assert event.event == "article_liked"
    assert event.props == {"article_id": 5}


def test_collect_attaches_user_when_authenticated(
    client: TestClient, db: Session, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/analytics/collect",
        headers=normal_user_token_headers,
        json={"path": "/profile", "visitor_id": "known-1"},
    )
    assert r.status_code == 204

    user = db.exec(select(User).where(User.email == settings.EMAIL_TEST_USER)).first()
    assert user is not None
    event = _latest_event(db, "known-1")
    assert event is not None
    assert event.user_id == user.id


def test_collect_truncates_oversized_strings(client: TestClient, db: Session) -> None:
    long_path = "/" + "x" * 5000
    r = client.post(
        f"{settings.API_V1_STR}/analytics/collect",
        json={"path": long_path, "visitor_id": "anon-4"},
    )
    assert r.status_code == 204
    event = _latest_event(db, "anon-4")
    assert event is not None
    assert event.path is not None
    assert len(event.path) == 2048
