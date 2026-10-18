"""Tests for signing in, and signing up, by email link."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta

import jwt
import pytest
import resend
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.dates import get_datetime_utc
from app.core.db.subscriber import NewsletterSubscriber
from app.core.db.user import User
from app.core.security import ALGORITHM, create_access_token
from app.core.settings import settings
from app.features.audience import service
from app.features.audience.tests.factories import (
    create_random_user,
    user_authentication_headers,
)
from tests.random_data import random_email

LINK_SENT = {"message": "Check your inbox for your sign-in link"}


def enable_resend_email(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    monkeypatch.setattr(
        "app.core.settings.settings.RESEND_API_KEY", "test-key", raising=False
    )
    monkeypatch.setattr(
        "app.core.settings.settings.EMAILS_FROM_EMAIL", "hello@example.com"
    )
    monkeypatch.setattr(resend.Contacts, "create", lambda *args, **kwargs: None)
    sent: list[dict[str, str]] = []
    monkeypatch.setattr(resend.Emails, "send", lambda payload: sent.append(payload))
    return sent


def test_link_request_emails_existing_user(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
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


def test_link_request_succeeds_when_send_fails(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable_resend_email(monkeypatch)

    def fail(_payload: dict[str, object]) -> None:
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


def _signed(user_id: uuid.UUID, key: str, expires_in: timedelta) -> str:
    payload = {"sub": str(user_id), "exp": get_datetime_utc() + expires_in}
    return jwt.encode(payload, key, algorithm=ALGORITHM)


@pytest.mark.parametrize(
    "make_token",
    [
        lambda user_id: create_access_token(user_id, timedelta(minutes=-1)),
        lambda user_id: _signed(user_id, "x" * 32, timedelta(minutes=5)),
        lambda user_id: _signed(user_id, settings.SECRET_KEY, timedelta(minutes=5))[
            :-2
        ],
    ],
    ids=["expired", "wrong-key", "tampered"],
)
def test_access_token_is_rejected(
    client: TestClient, db: Session, make_token: Callable[[uuid.UUID], str]
) -> None:
    user = create_random_user(db)
    r = client.post(
        f"{settings.API_V1_STR}/login/test-token",
        headers={"Authorization": f"Bearer {make_token(user.id)}"},
    )
    assert r.status_code == 403


def test_link_request_unknown_email_creates_account(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = enable_resend_email(monkeypatch)
    email = random_email()

    r = client.post(f"{settings.API_V1_STR}/login/link", json={"email": email})
    assert r.status_code == 200
    assert r.json() == LINK_SENT

    user = db.exec(select(User).where(User.email == email)).first()
    assert user
    assert user.full_name is None
    assert db.get(NewsletterSubscriber, email) is not None
    assert [m["to"] for m in sent] == [email]
    assert sent[0]["subject"] == "Welcome to Agentique"
    assert f"{settings.FRONTEND_HOST}/auth?token={user.login_token}" in sent[0]["html"]
    assert "expire" not in sent[0]["html"]

    db.delete(db.get(NewsletterSubscriber, email))
    db.commit()


def test_new_account_syncs_resend_contact(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("RESEND_AUDIENCE_ID", "test-audience")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        resend.Contacts, "create", lambda payload: calls.append(payload)
    )
    email = random_email()

    r = client.post(
        f"{settings.API_V1_STR}/login/link",
        json={"email": email, "utm_source": "hn"},
    )
    assert r.status_code == 200
    assert calls == [{"email": email, "audience_id": "test-audience"}]
    subscriber = db.get(NewsletterSubscriber, email)
    assert subscriber is not None
    assert subscriber.utm_source == "hn"

    db.delete(subscriber)
    db.commit()


def test_link_request_never_duplicates_an_account(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = enable_resend_email(monkeypatch)
    user = create_random_user(db)

    r = client.post(f"{settings.API_V1_STR}/login/link", json={"email": user.email})
    assert r.status_code == 200
    assert r.json() == LINK_SENT
    assert [m["subject"] for m in sent] == ["Sign in to Agentique"]
    assert len(db.exec(select(User).where(User.email == user.email)).all()) == 1


def test_link_request_invalid_email(client: TestClient) -> None:
    r = client.post(f"{settings.API_V1_STR}/login/link", json={"email": "nope"})
    assert r.status_code == 422
