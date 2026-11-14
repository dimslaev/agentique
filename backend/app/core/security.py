"""JWT access tokens, the sign-in link token and the MCP token."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.settings import settings

ALGORITHM = "HS256"


def create_access_token(subject: uuid.UUID, expires_delta: timedelta) -> str:
    expire = datetime.now(UTC) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def generate_login_token() -> str:
    """A random secret for the sign-in link: 43 url-safe characters, 256 bits."""
    return secrets.token_urlsafe(32)


MCP_TOKEN_PREFIX = "agq_"


def generate_mcp_token() -> str:
    """A random MCP token. The prefix lets a secret scanner recognise a leak."""
    return MCP_TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_mcp_token(token: str) -> str:
    """What is stored and looked up. Plain SHA-256, no salt or stretching: the
    token is 256 random bits, so there is nothing to guess."""
    return hashlib.sha256(token.encode()).hexdigest()
