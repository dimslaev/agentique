"""Shared pytest fixtures: test client, db session, and auth token headers."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.db.engine import engine
from app.core.db.event import AnalyticsEvent
from app.core.db.like import ArticleLike
from app.core.db.user import User
from app.core.settings import settings
from app.features.audience.service import init_db
from app.features.audience.tests.factories import (
    authentication_token_from_email,
    get_superuser_token_headers,
)
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        init_db(session)
        yield session
        statement = delete(ArticleLike)
        session.execute(statement)
        statement = delete(AnalyticsEvent)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(db: Session) -> dict[str, str]:
    return get_superuser_token_headers(db)


@pytest.fixture(scope="module")
def normal_user_token_headers(db: Session) -> dict[str, str]:
    return authentication_token_from_email(email=settings.EMAIL_TEST_USER, db=db)
