"""Tests for the account service."""

from __future__ import annotations

from sqlmodel import Session

from app.audience import service
from app.audience.tests.factories import create_random_user


def test_create_user_gets_a_login_token(db: Session) -> None:
    user = create_random_user(db)
    assert len(user.login_token) >= 43
    assert user.is_active is True
    assert user.is_superuser is False


def test_login_tokens_differ(db: Session) -> None:
    assert create_random_user(db).login_token != create_random_user(db).login_token


def test_get_user_by_login_token(db: Session) -> None:
    user = create_random_user(db)
    found = service.get_user_by_login_token(session=db, token=user.login_token)
    assert found is not None
    assert found.id == user.id
    assert service.get_user_by_login_token(session=db, token="nope") is None
