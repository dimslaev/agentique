"""Audience shapes: the reader account as the API reads and writes it, and the auth payloads."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr
from sqlmodel import Field, SQLModel

from app.core.db.user import UserBase

# ─── User ────────────────────────────────────────────────────────────────────


# Properties to receive via API on creation
class UserCreate(UserBase):
    pass


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


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
    utm_source: str | None = Field(default=None, max_length=255)


class MagicLogin(SQLModel):
    token: str = Field(max_length=64)
