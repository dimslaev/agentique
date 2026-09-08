"""The SQLAlchemy engine every session is opened against."""

from __future__ import annotations

from sqlmodel import create_engine

from app.platform.settings import settings

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
