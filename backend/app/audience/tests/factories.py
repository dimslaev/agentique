"""Factory for creating random User rows in tests."""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session

from app.audience import service
from app.audience.models import User, UserCreate
from app.platform.security import create_access_token
from app.platform.settings import settings
from tests.random_data import random_email


def user_authentication_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, expires_delta=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


def create_random_user(db: Session) -> User:
    return service.create_user(session=db, user_create=UserCreate(email=random_email()))


def authentication_token_from_email(*, email: str, db: Session) -> dict[str, str]:
    """
    Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    user = service.get_user_by_email(session=db, email=email)
    if not user:
        user = service.create_user(session=db, user_create=UserCreate(email=email))
    return user_authentication_headers(user)


def get_superuser_token_headers(db: Session) -> dict[str, str]:
    return authentication_token_from_email(email=settings.FIRST_SUPERUSER, db=db)
