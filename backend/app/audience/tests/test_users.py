"""Tests for signup and self-service account endpoints."""

from __future__ import annotations

import resend
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.audience.models import User
from app.audience.tests.factories import create_random_user, user_authentication_headers
from app.audience.tests.test_login import LINK_SENT, enable_resend_email
from app.newsletter.models import NewsletterSubscriber
from app.platform.settings import settings
from tests.random_data import random_email


def test_get_users_superuser_me(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=superuser_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"]
    assert current_user["email"] == settings.FIRST_SUPERUSER


def test_get_users_normal_user_me(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/users/me", headers=normal_user_token_headers)
    current_user = r.json()
    assert current_user
    assert current_user["is_active"] is True
    assert current_user["is_superuser"] is False
    assert current_user["email"] == settings.EMAIL_TEST_USER


def test_update_user_me(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    full_name = "Updated Name"
    email = random_email()
    data = {"full_name": full_name, "email": email}
    r = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 200
    updated_user = r.json()
    assert updated_user["email"] == email
    assert updated_user["full_name"] == full_name

    user_query = select(User).where(User.email == email)
    user_db = db.exec(user_query).first()
    assert user_db
    assert user_db.email == email
    assert user_db.full_name == full_name


def test_update_user_me_email_exists(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    user = create_random_user(db)

    data = {"email": user.email}
    r = client.patch(
        f"{settings.API_V1_STR}/users/me",
        headers=normal_user_token_headers,
        json=data,
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "User with this email already exists"


def test_delete_user_me(client: TestClient, db: Session) -> None:
    user = create_random_user(db)
    user_id = user.id
    headers = user_authentication_headers(user)

    r = client.delete(
        f"{settings.API_V1_STR}/users/me",
        headers=headers,
    )
    assert r.status_code == 200
    deleted_user = r.json()
    assert deleted_user["message"] == "User deleted successfully"
    result = db.exec(select(User).where(User.id == user_id)).first()
    assert result is None

    user_query = select(User).where(User.id == user_id)
    user_db = db.exec(user_query).first()
    assert user_db is None


def test_delete_user_me_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{settings.API_V1_STR}/users/me",
        headers=superuser_token_headers,
    )
    assert r.status_code == 403
    response = r.json()
    assert response["detail"] == "Super users are not allowed to delete themselves"


def test_signup_with_email_only(client: TestClient, db: Session, monkeypatch) -> None:
    sent = enable_resend_email(monkeypatch)
    email = random_email()

    r = client.post(f"{settings.API_V1_STR}/users/signup", json={"email": email})
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


def test_signup_syncs_resend_contact(
    client: TestClient, db: Session, monkeypatch
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("RESEND_AUDIENCE_ID", "test-audience")
    calls: list[dict] = []
    monkeypatch.setattr(
        resend.Contacts, "create", lambda payload: calls.append(payload)
    )
    email = random_email()

    r = client.post(
        f"{settings.API_V1_STR}/users/signup",
        json={"email": email, "utm_source": "hn"},
    )
    assert r.status_code == 200
    assert calls == [{"email": email, "audience_id": "test-audience"}]
    subscriber = db.get(NewsletterSubscriber, email)
    assert subscriber is not None
    assert subscriber.utm_source == "hn"

    db.delete(subscriber)
    db.commit()


def test_signup_existing_user_gets_sign_in_link(
    client: TestClient, db: Session, monkeypatch
) -> None:
    sent = enable_resend_email(monkeypatch)
    user = create_random_user(db)

    r = client.post(f"{settings.API_V1_STR}/users/signup", json={"email": user.email})
    assert r.status_code == 200
    assert r.json() == LINK_SENT
    assert [m["subject"] for m in sent] == ["Sign in to Agentique"]
    assert len(db.exec(select(User).where(User.email == user.email)).all()) == 1


def test_signup_invalid_email(client: TestClient) -> None:
    r = client.post(f"{settings.API_V1_STR}/users/signup", json={"email": "nope"})
    assert r.status_code == 422
