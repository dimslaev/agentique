"""The analytics endpoints: the ingest beacon and the admin report."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, delete, select

from app.core.dates import get_datetime_utc
from app.core.db.event import AnalyticsEvent
from app.core.db.factories import create_random_article, create_random_user
from app.core.db.user import User
from app.core.settings import settings

REPORT = f"{settings.API_V1_STR}/analytics/report"
BROWSER = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15"
PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile/15E148"


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


def test_collect_ignores_referer_header(client: TestClient, db: Session) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/analytics/collect",
        headers={"Referer": "https://agentique.ch/feed"},
        json={"path": "/feed", "visitor_id": "anon-5"},
    )
    assert r.status_code == 204
    event = _latest_event(db, "anon-5")
    assert event is not None
    assert event.referrer is None


def test_collect_drops_query_strings(client: TestClient, db: Session) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/analytics/collect",
        json={
            "path": "/auth?token=secret",
            "referrer": "https://agentique.ch/reset-password?token=secret#top",
            "visitor_id": "anon-6",
        },
    )
    assert r.status_code == 204
    event = _latest_event(db, "anon-6")
    assert event is not None
    assert event.path == "/auth"
    assert event.referrer == "https://agentique.ch/reset-password"


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


@pytest.fixture(autouse=True)
def empty_events(db: Session) -> Generator[None]:
    db.exec(delete(AnalyticsEvent))
    db.commit()
    yield


def _event(db: Session, **fields: object) -> None:
    fields.setdefault("user_agent", BROWSER)
    db.add(AnalyticsEvent(**fields))  # ty: ignore[invalid-argument-type]
    db.commit()


def _superuser(db: Session) -> User:
    return db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()


def test_report_requires_a_token(client: TestClient) -> None:
    assert client.get(REPORT).status_code == 401


def test_report_refuses_a_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(REPORT, headers=normal_user_token_headers)
    assert r.status_code == 403


def test_report_counts_outside_readers_only(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    _event(db, path="/", visitor_id="reader-1", referrer="https://www.google.com/")
    _event(db, path="/blog/x/", visitor_id="reader-1")
    _event(db, path="/", visitor_id="reader-2", user_agent=PHONE)
    _event(db, path="/", visitor_id="crawler", user_agent="Googlebot/2.1")
    _event(db, path="/", visitor_id="scanner", user_agent="Scanory/1.0")
    _event(db, path="/", visitor_id="no-agent", user_agent=None)
    # the admin's device stays the admin's after signing out
    _event(db, path="/", visitor_id="admin-laptop", user_id=_superuser(db).id)
    _event(db, path="/", visitor_id="admin-laptop")

    r = client.get(REPORT, headers=superuser_token_headers)
    assert r.status_code == 200
    report = r.json()
    # other tests leave users behind; they're covered on their own below
    del report["totals"]["users"], report["totals"]["signups"]
    assert report["totals"] == {
        "visitors": 2,
        "pageviews": 3,
        "returning_visitors": 0,
        "article_clicks": 0,
        "admin_pageviews": 2,
        "bot_pageviews": 3,
    }
    assert report["pages"][0] == {"label": "/", "count": 2, "visitors": 2}
    assert report["referrers"] == [
        {"label": "www.google.com", "count": 1, "visitors": 1}
    ]
    devices = {row["label"]: row["count"] for row in report["devices"]}
    assert devices == {"desktop": 2, "mobile": 1}


def test_report_window_and_returning_visitors(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    now = get_datetime_utc()
    _event(db, path="/", visitor_id="regular", created_at=now)
    _event(db, path="/", visitor_id="regular", created_at=now - timedelta(days=2))
    _event(db, path="/", visitor_id="lapsed", created_at=now - timedelta(days=40))

    report = client.get(
        REPORT, params={"days": 7}, headers=superuser_token_headers
    ).json()
    assert report["days"] == 7
    assert report["totals"]["visitors"] == 1
    assert report["totals"]["returning_visitors"] == 1
    assert len(report["daily"]) == 7
    assert report["daily"][-1]["day"] == now.date().isoformat()
    assert sum(d["pageviews"] for d in report["daily"]) == 2

    everything = client.get(REPORT, headers=superuser_token_headers).json()
    assert everything["days"] is None
    assert everything["totals"]["visitors"] == 2
    assert (
        everything["daily"][0]["day"] == (now - timedelta(days=40)).date().isoformat()
    )


def test_report_ranks_clicked_articles(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    article = create_random_article(db)
    for visitor in ("reader-1", "reader-2"):
        _event(
            db,
            event="article_click",
            path="/",
            visitor_id=visitor,
            props={"article_id": article.id, "score": 80},
        )
    # a client can send anything; it must not break the report
    _event(db, event="article_click", visitor_id="reader-3", props={"article_id": "x"})
    _event(db, event="filter_click", visitor_id="reader-1", props={"row": "From"})

    report = client.get(REPORT, headers=superuser_token_headers).json()
    assert report["totals"]["article_clicks"] == 3
    assert report["articles"] == [
        {
            "article_id": str(article.id),
            "title": article.title,
            "clicks": 2,
            "visitors": 2,
        },
        {"article_id": "x", "title": None, "clicks": 1, "visitors": 1},
    ]
    events = {row["label"]: row["count"] for row in report["events"]}
    assert events == {"article_click": 3, "filter_click": 1}


def test_report_counts_registered_readers(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    def totals(days: int | None) -> dict[str, int]:
        params = {"days": days} if days else {}
        body = client.get(REPORT, headers=superuser_token_headers, params=params)
        return {k: int(v) for k, v in body.json()["totals"].items()}

    before, before_all = totals(7), totals(None)
    create_random_user(db)
    old = create_random_user(db)
    old.created_at = get_datetime_utc() - timedelta(days=30)
    db.add(old)
    db.commit()

    after, after_all = totals(7), totals(None)
    assert after["signups"] - before["signups"] == 1
    assert after["users"] - before["users"] == 2
    assert after_all["signups"] - before_all["signups"] == 2
    assert after_all["users"] == after_all["signups"]
