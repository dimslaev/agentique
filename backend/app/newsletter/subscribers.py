"""Adding an email to the newsletter: the subscriber row and the Resend contact."""

from __future__ import annotations

import logging
import os

import resend
from sqlmodel import Session

from app.newsletter.models import NewsletterSubscriber

logger = logging.getLogger(__name__)


def subscribe(*, session: Session, email: str, utm_source: str | None = None) -> None:
    """Add an email to the newsletter. An address already on it is left as is."""
    if session.get(NewsletterSubscriber, email) is None:
        session.add(NewsletterSubscriber(email=email, utm_source=utm_source))
        session.commit()

    api_key = os.getenv("RESEND_API_KEY")
    audience_id = os.getenv("RESEND_AUDIENCE_ID")
    if api_key and audience_id:
        resend.api_key = api_key
        try:
            resend.Contacts.create({"email": email, "audience_id": audience_id})
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"Resend contact create failed for {email}: {e}")
