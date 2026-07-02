import resend
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models_agentique import NewsletterSubscriber
from tests.utils.utils import random_email

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
