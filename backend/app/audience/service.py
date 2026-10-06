"""Account service: create, look up and update a reader's account."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlmodel import Session, col, select

from app.audience.models import ArticleLike, User, UserCreate, UserUpdateMe
from app.catalog.models import Article
from app.platform.dates import get_datetime_utc
from app.platform.security import generate_login_token
from app.platform.settings import settings

LOGIN_LINK_EXPIRE_MINUTES = 60


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(user_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def issue_login_token(*, session: Session, db_user: User) -> str:
    """A fresh token for a sign-in link. Any link sent before stops working."""
    token = generate_login_token()
    db_user.login_token = token
    db_user.login_token_expires_at = get_datetime_utc() + timedelta(
        minutes=LOGIN_LINK_EXPIRE_MINUTES
    )
    session.add(db_user)
    session.commit()
    return token


def get_user_by_login_token(*, session: Session, token: str) -> User | None:
    """The account a sign-in link belongs to, while the link still works."""
    statement = select(User).where(
        User.login_token == token,
        col(User.login_token_expires_at) > get_datetime_utc(),
    )
    return session.exec(statement).first()


def update_profile(*, session: Session, db_user: User, changes: UserUpdateMe) -> User:
    """Apply a reader's own edits to their name and email."""
    db_user.sqlmodel_update(changes.model_dump(exclude_unset=True))
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def delete_account(*, session: Session, db_user: User) -> None:
    session.delete(db_user)
    session.commit()


def like_article(*, session: Session, user_id: uuid.UUID, article_id: int) -> bool:
    """Record a like. False means the article does not exist — nothing was written."""
    if not session.get(Article, article_id):
        return False
    if not session.get(ArticleLike, (user_id, article_id)):
        session.add(ArticleLike(user_id=user_id, article_id=article_id))
        session.commit()
    return True


def unlike_article(*, session: Session, user_id: uuid.UUID, article_id: int) -> None:
    """Remove a like. Unliking something never liked is a no-op, not an error."""
    existing = session.get(ArticleLike, (user_id, article_id))
    if existing:
        session.delete(existing)
        session.commit()


def init_db(session: Session) -> None:
    """Create the configured first superuser if it isn't there yet.

    Lives with the account model rather than beside the engine: it is a
    domain operation that happens to run at startup, not database plumbing.
    """
    user = get_user_by_email(session=session, email=settings.FIRST_SUPERUSER)
    if not user:
        create_user(
            session=session,
            user_create=UserCreate(email=settings.FIRST_SUPERUSER, is_superuser=True),
        )
