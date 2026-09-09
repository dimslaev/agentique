"""Account service: create, look up, update and authenticate a reader's account."""

from __future__ import annotations

import uuid

from sqlmodel import Session, select

from app.audience.models import (
    ArticleLike,
    User,
    UserCreate,
    UserUpdate,
    UserUpdateMe,
)
from app.catalog.models import Article
from app.platform.security import get_password_hash, verify_password
from app.platform.settings import settings


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data: dict[str, str] = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user


def update_profile(*, session: Session, db_user: User, changes: UserUpdateMe) -> User:
    """Apply a reader's own edits to their name and email."""
    db_user.sqlmodel_update(changes.model_dump(exclude_unset=True))
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def password_matches(user: User, password: str) -> bool:
    verified, _ = verify_password(password, user.hashed_password)
    return verified


def set_password(*, session: Session, db_user: User, password: str) -> None:
    db_user.hashed_password = get_password_hash(password)
    session.add(db_user)
    session.commit()


def delete_account(*, session: Session, db_user: User) -> None:
    session.delete(db_user)
    session.commit()


def like_article(*, session: Session, user_id: uuid.UUID, article_id: int) -> bool:
    """Record a like. False means the article does not exist — nothing was written."""
    if not session.get(Article, article_id):
        return False
    if not session.get(ArticleLike, (user_id, article_id)):
        session.add(ArticleLike(user_id=user_id, article_id=article_id))
        session.commit()
    return True


def unlike_article(*, session: Session, user_id: uuid.UUID, article_id: int) -> None:
    """Remove a like. Unliking something never liked is a no-op, not an error."""
    existing = session.get(ArticleLike, (user_id, article_id))
    if existing:
        session.delete(existing)
        session.commit()


def init_db(session: Session) -> None:
    """Create the configured first superuser if it isn't there yet.

    Lives with the account model rather than beside the engine: it is a
    domain operation that happens to run at startup, not database plumbing.
    """
    user = get_user_by_email(session=session, email=settings.FIRST_SUPERUSER)
    if not user:
        create_user(
            session=session,
            user_create=UserCreate(
                email=settings.FIRST_SUPERUSER,
                password=settings.FIRST_SUPERUSER_PASSWORD,
                is_superuser=True,
            ),
        )
