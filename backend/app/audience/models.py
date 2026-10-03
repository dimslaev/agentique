"""Audience schema: the reader account, its auth payloads, and the likes it leaves."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr
from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.platform.dates import get_datetime_utc

# ─── User ────────────────────────────────────────────────────────────────────


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    pass


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    utm_source: str | None = Field(default=None, max_length=255)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # The secret in the sign-in link. It never expires, so every link ever
    # emailed keeps working until this value is replaced.
    login_token: str = Field(unique=True, index=True, max_length=64)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# ─── Auth payloads ───────────────────────────────────────────────────────────


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class SignInRequest(SQLModel):
    email: EmailStr = Field(max_length=255)


class MagicLogin(SQLModel):
    token: str = Field(max_length=64)


# ─── ArticleLike ─────────────────────────────────────────────────────────────
# A like is a reader action: its lifecycle follows the user, not the article,
# so it lives here rather than in the catalog.


class ArticleLike(SQLModel, table=True):
    __tablename__ = "article_like"
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    article_id: int = Field(foreign_key="article.id", primary_key=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
