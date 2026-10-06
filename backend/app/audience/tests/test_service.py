"""Tests for the account service."""

from __future__ import annotations

from sqlmodel import Session

from app.audience import service
from app.audience.tests.factories import create_random_user


def test_issue_login_token(db: Session) -> None:
    user = create_random_user(db)
    assert len(service.issue_login_token(session=db, db_user=user)) >= 43
    assert user.is_active is True
    assert user.is_superuser is False


def test_login_tokens_differ(db: Session) -> None:
    user = create_random_user(db)
    first = service.issue_login_token(session=db, db_user=user)
    assert service.issue_login_token(session=db, db_user=user) != first


def test_get_user_by_login_token(db: Session) -> None:
    user = create_random_user(db)
    token = service.issue_login_token(session=db, db_user=user)
    found = service.get_user_by_login_token(session=db, token=token)
    assert found is not None
    assert found.id == user.id
    assert service.get_user_by_login_token(session=db, token="nope") is None
