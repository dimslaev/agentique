import logging
import os
from typing import Any

import resend
from fastapi import APIRouter, HTTPException

from app.api.deps import SessionDep
from app.models_agentique import (
    NewsletterSubscriber,
    NewsletterSubscribeRequest,
    NewsletterSubscribeResponse,
    get_datetime_utc,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/newsletter", tags=["newsletter"])


@router.post("/subscribe", response_model=NewsletterSubscribeResponse)
def subscribe(session: SessionDep, body: NewsletterSubscribeRequest) -> Any:
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

    return NewsletterSubscribeResponse(ok=True)
