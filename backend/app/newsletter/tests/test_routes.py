"""Tests for the newsletter signup endpoint."""

from __future__ import annotations

import resend
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.newsletter.models import NewsletterSubscriber
from app.platform.settings import settings
from tests.random_data import random_email

NEWSLETTER_URL = "/api/newsletter/subscribe"


def test_subscribe_valid_email_defaults_to_all(
    client: TestClient, db: Session, monkeypatch
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("RESEND_AUDIENCE_ID", "test-audience")
    calls = []
    monkeypatch.setattr(
        resend.Contacts, "create", lambda payload: calls.append(payload)
    )
    email = random_email()

    r = client.post(NEWSLETTER_URL, json={"email": email})
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    subscriber = db.get(NewsletterSubscriber, email)
    assert subscriber is not None
    assert subscriber.categories == ["all"]
    assert calls == [{"email": email, "audience_id": "test-audience"}]

    db.delete(subscriber)
    db.commit()


def test_subscribe_with_categories_and_custom_category(
    client: TestClient, db: Session, monkeypatch
) -> None:
    monkeypatch.setattr(resend.Contacts, "create", lambda *args, **kwargs: None)
    email = random_email()

    r = client.post(
        NEWSLETTER_URL,
        json={
            "email": email,
            "categories": ["dev", "research"],
            "customCategory": "rust",
        },
    )
    assert r.status_code == 200

    subscriber = db.get(NewsletterSubscriber, email)
    assert subscriber is not None
    assert subscriber.categories == ["dev", "research"]
    assert subscriber.custom_category == "rust"

    db.delete(subscriber)
    db.commit()


def test_subscribe_invalid_email_returns_400(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(resend.Contacts, "create", lambda *args, **kwargs: None)

    r = client.post(NEWSLETTER_URL, json={"email": "not-an-email"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Valid email is required"


def _enable_resend_email(monkeypatch) -> list[dict]:
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


def test_subscribe_sends_welcome_only_to_new_address(
    client: TestClient, db: Session, monkeypatch
) -> None:
    sent = _enable_resend_email(monkeypatch)
    email = random_email()

    assert client.post(NEWSLETTER_URL, json={"email": email}).status_code == 200
    assert [m["to"] for m in sent] == [email]
    assert sent[0]["subject"] == "Welcome to Agentique"
    assert f"{settings.FRONTEND_HOST}/feed" in sent[0]["html"]

    r = client.post(NEWSLETTER_URL, json={"email": email, "categories": ["dev"]})
    assert r.status_code == 200
    assert len(sent) == 1

    subscriber = db.get(NewsletterSubscriber, email)
    assert subscriber is not None
    db.delete(subscriber)
    db.commit()


def test_subscribe_succeeds_when_welcome_fails(
    client: TestClient, db: Session, monkeypatch
) -> None:
    _enable_resend_email(monkeypatch)

    def fail(_payload: dict) -> None:
        raise RuntimeError("resend down")

    monkeypatch.setattr(resend.Emails, "send", fail)
    email = random_email()

    r = client.post(NEWSLETTER_URL, json={"email": email})
    assert r.status_code == 200

    subscriber = db.get(NewsletterSubscriber, email)
    assert subscriber is not None
    db.delete(subscriber)
    db.commit()
