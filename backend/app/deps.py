"""FastAPI dependency wiring: DB session, current-user, and auth shared by every route module."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.audience.models import TokenPayload, User
from app.platform import security
from app.platform.db import engine
from app.platform.settings import settings

reusable_bearer = HTTPBearer()


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[HTTPAuthorizationCredentials, Depends(reusable_bearer)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token.credentials, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_user_optional(request: Request, session: SessionDep) -> User | None:
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        return None

    user = session.get(User, token_data.sub)
    if not user or not user.is_active:
        return None
    return user


CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]
