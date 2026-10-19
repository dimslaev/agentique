"""Signing up and in by email link, and swapping the link for an access token."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core import security
from app.core.db.user import User
from app.core.settings import settings
from app.entry.api.deps import CurrentUser, SessionDep
from app.features.audience import service
from app.features.audience.model import (
    MagicLogin,
    Message,
    SignInRequest,
    Token,
    UserCreate,
    UserPublic,
)
from app.features.newsletter.service import subscribe

router = APIRouter(tags=["login"])

LINK_SENT = "Check your inbox for your sign-in link"


@router.post("/login/link")
def request_sign_in_link(
    session: SessionDep, body: SignInRequest, background_tasks: BackgroundTasks
) -> Message:
    """
    Email a sign-in link. An unknown email first gets an account and a
    newsletter subscription, and the link comes in a welcome email.
    """
    user = service.get_user_by_email(session=session, email=body.email)
    is_new = user is None
    if user is None:
        user = service.create_user(
            session=session, user_create=UserCreate(email=body.email)
        )
        subscribe(session=session, email=user.email, utm_source=body.utm_source)
    elif not user.is_active:
        return Message(message=LINK_SENT)
    token = service.issue_login_token(session=session, db_user=user)
    email = (
        service.generate_welcome_email(token)
        if is_new
        else service.generate_sign_in_email(token)
    )
    background_tasks.add_task(service.send_link_email, user.email, email, token)
    return Message(message=LINK_SENT)


@router.post("/login/token")
def login_with_link(session: SessionDep, body: MagicLogin) -> Token:
    """
    Swap the token from a sign-in link for an access token
    """
    user = service.get_user_by_login_token(session=session, token=body.token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid sign-in link")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return _access_token(user)


@router.post("/login/refresh")
def refresh_token(current_user: CurrentUser) -> Token:
    """
    Renew the access token
    """
    return _access_token(current_user)


def _access_token(user: User) -> Token:
    return Token(
        access_token=security.create_access_token(
            user.id,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
    )


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> User:
    """
    Test access token
    """
    return current_user
