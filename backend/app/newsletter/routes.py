"""Newsletter signup endpoint: captures an email and syncs it to Resend."""

from __future__ import annotations

import logging
import os

import resend
from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.deps import SessionDep
from app.newsletter.models import (
    NewsletterSubscriber,
    NewsletterSubscribeRequest,
    NewsletterSubscribeResponse,
)
from app.platform.dates import get_datetime_utc
from app.platform.email import generate_newsletter_welcome_email, send_email
from app.platform.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/newsletter", tags=["newsletter"])


def _send_welcome(email: str) -> None:
    # Runs after the response: a failed send must not fail the signup, which is
    # already saved.
    email_data = generate_newsletter_welcome_email()
    try:
        send_email(
            email_to=email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    except Exception as e:
        logger.error(f"Newsletter welcome email failed for {email}: {e}")


@router.post("/subscribe", response_model=NewsletterSubscribeResponse)
def subscribe(
    session: SessionDep,
    body: NewsletterSubscribeRequest,
    background_tasks: BackgroundTasks,
) -> NewsletterSubscribeResponse:
    if "@" not in body.email:
        raise HTTPException(status_code=400, detail="Valid email is required")

    categories = body.categories if body.categories else ["all"]

    existing = session.get(NewsletterSubscriber, body.email)
    subscriber = NewsletterSubscriber(
        email=body.email,
        categories=categories,
        custom_category=body.customCategory,
        utm_source=body.utm_source,
        created_at=existing.created_at if existing else get_datetime_utc(),
        updated_at=get_datetime_utc(),
    )
    session.merge(subscriber)
    session.commit()

    api_key = os.getenv("RESEND_API_KEY")
    audience_id = os.getenv("RESEND_AUDIENCE_ID")
    if api_key and audience_id:
        resend.api_key = api_key
        try:
            resend.Contacts.create({"email": body.email, "audience_id": audience_id})
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"Resend contact create failed for {body.email}: {e}")

    # The form doubles as "update your preferences", so only a new address gets
    # the welcome.
    if existing is None and settings.emails_enabled:
        background_tasks.add_task(_send_welcome, body.email)

    return NewsletterSubscribeResponse(ok=True)
