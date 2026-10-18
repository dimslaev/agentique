"""Shared pytest fixtures: test clients, db session, auth token headers, and the
MCP write scope."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from fastmcp.server.auth import AccessToken
from sqlmodel import Session, col, delete, func, select

from app.core.db.article import Article
from app.core.db.engine import engine
from app.core.db.event import AnalyticsEvent
from app.core.db.factories import (
    authentication_token_from_email,
    get_superuser_token_headers,
    random_email,
)
from app.core.db.like import ArticleLike
from app.core.db.publisher import Publisher
from app.core.db.story import Story, StoryArticle
from app.core.db.user import User
from app.core.settings import settings
from app.entry.mcp import auth
from app.features.audience.service import init_db
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


@pytest.fixture(scope="module")
def auth_client(db: Session) -> Generator[TestClient]:
    """A TestClient that sends a logged-in reader's bearer token on every request.

    Reads are public; the token only decides whether `liked_by_me` is filled in.
    """
    headers = authentication_token_from_email(email=random_email(), db=db)
    with TestClient(app) as c:
        c.headers.update(headers)
        yield c


@pytest.fixture
def curator(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer the MCP tools' scope check as the curation agent's write token."""
    monkeypatch.setattr(
        auth,
        "get_access_token",
        lambda: AccessToken(token="t", client_id="c", scopes=[auth.WRITE_SCOPE]),
    )


@pytest.fixture
def made(db: Session) -> Generator[dict[str, list[int]]]:
    """Ids of what a test created, deleted afterwards with every story made
    meanwhile, so the next test starts from the same rows."""
    created: dict[str, list[int]] = {"articles": [], "publishers": []}
    before = db.exec(select(func.max(Story.id))).one() or 0
    yield created
    db.rollback()
    ours = select(Story.id).where(col(Story.id) > before)
    db.exec(delete(StoryArticle).where(col(StoryArticle.story_id).in_(ours)))
    db.exec(delete(Story).where(col(Story.id) > before))
    db.exec(delete(Article).where(col(Article.id).in_(created["articles"])))
    db.exec(delete(Publisher).where(col(Publisher.id).in_(created["publishers"])))
    db.commit()
