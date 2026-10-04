"""Tests for the admin analytics report."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.analytics.models import AnalyticsEvent
from app.audience.models import User
from app.catalog.tests.factories import create_random_article
from app.platform.dates import get_datetime_utc
from app.platform.settings import settings

REPORT = f"{settings.API_V1_STR}/analytics/report"
BROWSER = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15"
PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile/15E148"


@pytest.fixture(autouse=True)
def empty_events(db: Session) -> Generator[None]:
    db.exec(delete(AnalyticsEvent))
    db.commit()
    yield


def _event(db: Session, **fields: object) -> None:
    fields.setdefault("user_agent", BROWSER)
    db.add(AnalyticsEvent(**fields))  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
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
    _event(db, path="/", visitor_id="no-agent", user_agent=None)
    # the admin's device stays the admin's after signing out
    _event(db, path="/", visitor_id="admin-laptop", user_id=_superuser(db).id)
    _event(db, path="/", visitor_id="admin-laptop")

    r = client.get(REPORT, headers=superuser_token_headers)
    assert r.status_code == 200
    report = r.json()
    assert report["totals"] == {
        "visitors": 2,
        "pageviews": 3,
        "returning_visitors": 0,
        "article_clicks": 0,
        "admin_pageviews": 2,
        "bot_pageviews": 2,
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
