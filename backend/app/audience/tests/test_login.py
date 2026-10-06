"""Tests for signing in by email link."""

from __future__ import annotations

from datetime import timedelta

import resend
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.audience import service
from app.audience.tests.factories import (
    create_random_user,
    user_authentication_headers,
)
from app.platform.dates import get_datetime_utc
from app.platform.settings import settings
from tests.random_data import random_email

LINK_SENT = {"message": "Check your inbox for your sign-in link"}


def enable_resend_email(monkeypatch) -> list[dict]:
    monkeypatch.setattr(
        "app.platform.settings.settings.RESEND_API_KEY", "test-key", raising=False
    )
    monkeypatch.setattr(
        "app.platform.settings.settings.EMAILS_FROM_EMAIL", "hello@example.com"
    )
    monkeypatch.setattr(resend.Contacts, "create", lambda *args, **kwargs: None)
    sent: list[dict] = []
    monkeypatch.setattr(resend.Emails, "send", lambda payload: sent.append(payload))
    return sent


def test_link_request_emails_existing_user(
    client: TestClient, db: Session, monkeypatch
) -> None:
    sent = enable_resend_email(monkeypatch)
    user = create_random_user(db)

    r = client.post(f"{settings.API_V1_STR}/login/link", json={"email": user.email})
    assert r.status_code == 200
    assert r.json() == LINK_SENT
    assert [m["to"] for m in sent] == [user.email]
    assert sent[0]["subject"] == "Sign in to Agentique"
    db.refresh(user)
    assert f"{settings.FRONTEND_HOST}/auth?token={user.login_token}" in sent[0]["html"]
    assert "expire" not in sent[0]["html"]


def test_new_link_replaces_the_old_one(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    old = service.issue_login_token(session=db, db_user=user)

    client.post(f"{settings.API_V1_STR}/login/link", json={"email": user.email})
    db.refresh(user)

    url = f"{settings.API_V1_STR}/login/token"
    assert client.post(url, json={"token": old}).status_code == 400
    assert client.post(url, json={"token": user.login_token}).status_code == 200


def test_link_request_unknown_email_sends_nothing(
    client: TestClient, monkeypatch
) -> None:
    sent = enable_resend_email(monkeypatch)

    r = client.post(f"{settings.API_V1_STR}/login/link", json={"email": random_email()})
    assert r.status_code == 200
    assert r.json() == LINK_SENT
    assert sent == []


def test_link_request_succeeds_when_send_fails(
    client: TestClient, db: Session, monkeypatch
) -> None:
    enable_resend_email(monkeypatch)

    def fail(_payload: dict) -> None:
        raise RuntimeError("resend down")

    monkeypatch.setattr(resend.Emails, "send", fail)
    user = create_random_user(db)

    r = client.post(f"{settings.API_V1_STR}/login/link", json={"email": user.email})
    assert r.status_code == 200


def test_login_with_link(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    token = service.issue_login_token(session=db, db_user=user)

    r = client.post(f"{settings.API_V1_STR}/login/token", json={"token": token})
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=headers)
    assert r.json()["email"] == user.email


def test_refresh_token(client: TestClient, db: Session) -> None:
    headers = user_authentication_headers(create_random_user(db))

    r = client.post(f"{settings.API_V1_STR}/login/refresh", headers=headers)
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get(f"{settings.API_V1_STR}/users/me", headers=headers).is_success


def test_login_with_link_works_twice(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    token = service.issue_login_token(session=db, db_user=user)
    url = f"{settings.API_V1_STR}/login/token"

    assert client.post(url, json={"token": token}).status_code == 200
    assert client.post(url, json={"token": token}).status_code == 200


def test_login_with_expired_link(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    token = service.issue_login_token(session=db, db_user=user)
    user.login_token_expires_at = get_datetime_utc() - timedelta(seconds=1)
    db.add(user)
    db.commit()

    r = client.post(f"{settings.API_V1_STR}/login/token", json={"token": token})
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid sign-in link"


def test_login_with_invalid_link(client: TestClient) -> None:
    r = client.post(f"{settings.API_V1_STR}/login/token", json={"token": "nope"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid sign-in link"


def test_login_with_link_inactive_user(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    token = service.issue_login_token(session=db, db_user=user)
    user.is_active = False
    db.add(user)
    db.commit()

    r = client.post(f"{settings.API_V1_STR}/login/token", json={"token": token})
    assert r.status_code == 400
    assert r.json()["detail"] == "Inactive user"


def test_use_access_token(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/login/test-token",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    assert "email" in r.json()
