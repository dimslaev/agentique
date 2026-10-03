"""Tests for adding an email to the newsletter."""

from __future__ import annotations

import resend
from sqlmodel import Session

from app.newsletter.models import NewsletterSubscriber
from app.newsletter.subscribers import subscribe
from tests.random_data import random_email


def test_subscribe_defaults_to_all(db: Session, monkeypatch) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    email = random_email()

    subscribe(session=db, email=email)

    subscriber = db.get(NewsletterSubscriber, email)
    assert subscriber is not None
    assert subscriber.categories == ["all"]
    db.delete(subscriber)
    db.commit()


def test_subscribe_keeps_an_existing_row(db: Session, monkeypatch) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    email = random_email()
    db.add(NewsletterSubscriber(email=email, categories=["dev"], utm_source="x"))
    db.commit()

    subscribe(session=db, email=email, utm_source="y")

    subscriber = db.get(NewsletterSubscriber, email)
    assert subscriber is not None
    db.refresh(subscriber)
    assert subscriber.categories == ["dev"]
    assert subscriber.utm_source == "x"
    db.delete(subscriber)
    db.commit()


def test_subscribe_ignores_existing_resend_contact(db: Session, monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "test-key")
    monkeypatch.setenv("RESEND_AUDIENCE_ID", "test-audience")

    def exists(_payload: dict) -> None:
        raise RuntimeError("Contact already exists")

    monkeypatch.setattr(resend.Contacts, "create", exists)
    email = random_email()

    subscribe(session=db, email=email)

    subscriber = db.get(NewsletterSubscriber, email)
    assert subscriber is not None
    db.delete(subscriber)
    db.commit()
