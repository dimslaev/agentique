"""Reader-facing endpoints: logging in, the signed-in account, and liking an article.

Three routers rather than one, because each carries its own OpenAPI tag and the
generated client names its functions after that tag.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.audience import service
from app.audience.models import (
    Message,
    NewPassword,
    Token,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UserUpdate,
    UserUpdateMe,
)
from app.catalog.articles import list_liked_articles
from app.catalog.models import ArticlesPublic
from app.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.platform import security
from app.platform.email import generate_reset_password_email, send_email
from app.platform.settings import settings

logger = logging.getLogger(__name__)

login_router = APIRouter(tags=["login"])
users_router = APIRouter(prefix="/users", tags=["users"])
likes_router = APIRouter(tags=["likes"])


# ─── Login and password recovery ────────────────────────────────────────────


@login_router.post("/login/access-token")
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = service.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@login_router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> User:
    """
    Test access token
    """
    return current_user


@login_router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    """
    Password Recovery
    """
    user = service.get_user_by_email(session=session, email=email)

    # Always return the same response to prevent email enumeration attacks
    # Only send email if user actually exists
    if user:
        password_reset_token = security.generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        if settings.ENVIRONMENT == "development":
            logger.info(
                "[dev] Password reset link for %s: %s/reset-password?token=%s",
                email,
                settings.FRONTEND_HOST,
                password_reset_token,
            )
        if settings.emails_enabled:
            send_email(
                email_to=user.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@login_router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    email = security.verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = service.get_user_by_email(session=session, email=email)
    if not user:
        # Don't reveal that the user doesn't exist - use same error as invalid token
        raise HTTPException(status_code=400, detail="Invalid token")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    service.update_user(
        session=session,
        db_user=user,
        user_in=UserUpdate(password=body.new_password),
    )
    return Message(message="Password updated successfully")


@login_router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> HTMLResponse:
    """
    HTML Content for Password Recovery
    """
    user = service.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = security.generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )


# ─── The signed-in account ──────────────────────────────────────────────────


@users_router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> User:
    """
    Update own user.
    """
    if user_in.email:
        existing_user = service.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    return service.update_profile(
        session=session, db_user=current_user, changes=user_in
    )


@users_router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Message:
    """
    Update own password.
    """
    if not service.password_matches(current_user, body.current_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    service.set_password(
        session=session, db_user=current_user, password=body.new_password
    )
    return Message(message="Password updated successfully")


@users_router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> User:
    """
    Get current user.
    """
    return current_user


@users_router.delete("/me", response_model=Message)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Message:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    service.delete_account(session=session, db_user=current_user)
    return Message(message="User deleted successfully")


@users_router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> User:
    """
    Create new user without the need to be logged in.
    """
    if service.get_user_by_email(session=session, email=user_in.email):
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    return service.create_user(
        session=session, user_create=UserCreate.model_validate(user_in)
    )


# ─── Likes ──────────────────────────────────────────────────────────────────


@likes_router.put("/articles/{article_id}/like")
def like_article(
    session: SessionDep, current_user: CurrentUser, article_id: int
) -> dict[str, bool]:
    liked = service.like_article(
        session=session, user_id=current_user.id, article_id=article_id
    )
    if not liked:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"ok": True}


@likes_router.delete("/articles/{article_id}/like")
def unlike_article(
    session: SessionDep, current_user: CurrentUser, article_id: int
) -> dict[str, bool]:
    service.unlike_article(
        session=session, user_id=current_user.id, article_id=article_id
    )
    return {"ok": True}


@likes_router.get("/me/liked-articles", response_model=ArticlesPublic)
def read_liked_articles(
    session: SessionDep, current_user: CurrentUser
) -> ArticlesPublic:
    return list_liked_articles(session, current_user.id)
