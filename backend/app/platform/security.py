"""JWT access tokens and the permanent sign-in link token."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.platform.settings import settings

ALGORITHM = "HS256"


def create_access_token(subject: uuid.UUID, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def generate_login_token() -> str:
    """A random secret for the sign-in link: 43 url-safe characters, 256 bits."""
    return secrets.token_urlsafe(32)
