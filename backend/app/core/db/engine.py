"""The one engine for every session, and the session a request uses."""

from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.settings import settings

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def get_session() -> Generator[Session]:
    with Session(engine) as session:
        yield session
