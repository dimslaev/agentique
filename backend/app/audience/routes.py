"""Reader-facing endpoints: signing up and in by email link, the signed-in account, and liking an article.

Three routers rather than one, because each carries its own OpenAPI tag and the
generated client names its functions after that tag.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.audience import service
from app.audience.models import (
    MagicLogin,
    Message,
    SignInRequest,
    Token,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UserUpdateMe,
)
from app.catalog.articles import list_liked_articles
from app.catalog.models import ArticlesPublic
from app.deps import CurrentUser, SessionDep
from app.newsletter.subscribers import subscribe
from app.platform import security
from app.platform.email import (
    EmailData,
    generate_sign_in_email,
    generate_welcome_email,
    send_email,
    sign_in_link,
)
from app.platform.settings import settings

logger = logging.getLogger(__name__)

login_router = APIRouter(tags=["login"])
users_router = APIRouter(prefix="/users", tags=["users"])
likes_router = APIRouter(tags=["likes"])


# ─── Sign-in links ──────────────────────────────────────────────────────────

LINK_SENT = "Check your inbox for your sign-in link"


def _send_link_email(email_to: str, email_data: EmailData, login_token: str) -> None:
    # Runs after the response: a failed send must not fail the request, and the
    # caller's answer must not depend on whether the account exists.
    if settings.ENVIRONMENT == "development":
        logger.info(
            "[dev] Sign-in link for %s: %s", email_to, sign_in_link(login_token)
        )
    if not settings.emails_enabled:
        return
    try:
        send_email(
            email_to=email_to,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    except Exception as e:
        logger.error(f"Sign-in email failed for {email_to}: {e}")


@login_router.post("/login/link")
def request_sign_in_link(
    session: SessionDep, body: SignInRequest, background_tasks: BackgroundTasks
) -> Message:
    """
    Email the sign-in link to an existing account
    """
    user = service.get_user_by_email(session=session, email=body.email)
    # Same answer whether or not the account exists, so the endpoint can't be
    # used to find out who has one.
    if user and user.is_active:
        token = service.issue_login_token(session=session, db_user=user)
        background_tasks.add_task(
            _send_link_email, user.email, generate_sign_in_email(token), token
        )
    return Message(message=LINK_SENT)


@login_router.post("/login/token")
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


@login_router.post("/login/refresh")
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


@login_router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> User:
    """
    Test access token
    """
    return current_user


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


@users_router.post("/signup")
def register_user(
    session: SessionDep, user_in: UserRegister, background_tasks: BackgroundTasks
) -> Message:
    """
    Create an account from an email alone, add it to the newsletter, and email
    a sign-in link. An existing account just gets a new link.
    """
    user = service.get_user_by_email(session=session, email=user_in.email)
    if user:
        if user.is_active:
            token = service.issue_login_token(session=session, db_user=user)
            background_tasks.add_task(
                _send_link_email, user.email, generate_sign_in_email(token), token
            )
        return Message(message=LINK_SENT)
    user = service.create_user(
        session=session, user_create=UserCreate(email=user_in.email)
    )
    subscribe(session=session, email=user.email, utm_source=user_in.utm_source)
    token = service.issue_login_token(session=session, db_user=user)
    background_tasks.add_task(
        _send_link_email, user.email, generate_welcome_email(token), token
    )
    return Message(message=LINK_SENT)


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
