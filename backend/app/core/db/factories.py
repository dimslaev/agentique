"""Test factories: random users, publishers, tags and articles.

They write rows straight to the tables, so a test anywhere can use them without
importing a feature.
"""

from __future__ import annotations

import random
import string
from datetime import timedelta

from sqlmodel import Session, select

from app.core.db.article import Article, ArticleKind
from app.core.db.publisher import Publisher, PublisherKind, slugify
from app.core.db.tag import ArticleTag, Tag
from app.core.db.user import User
from app.core.security import create_access_token
from app.core.settings import settings


def random_lower_string() -> str:
    """Random enough that two tests never collide on a unique column."""
    return "".join(random.choices(string.ascii_lowercase, k=32))


def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"


def create_user(db: Session, email: str) -> User:
    user = User(email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_random_user(db: Session) -> User:
    return create_user(db, random_email())


def user_authentication_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, expires_delta=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


def authentication_token_from_email(*, email: str, db: Session) -> dict[str, str]:
    """Headers for the user with this email, created first if it isn't there."""
    user = db.exec(select(User).where(User.email == email)).first()
    if not user:
        user = create_user(db, email)
    return user_authentication_headers(user)


def get_superuser_token_headers(db: Session) -> dict[str, str]:
    return authentication_token_from_email(email=settings.FIRST_SUPERUSER, db=db)


def create_random_publisher(db: Session, **overrides: object) -> Publisher:
    name = random_lower_string()
    defaults: dict[str, object] = {
        "slug": slugify(name),
        "name": name,
        "kind": PublisherKind.community,
    }
    defaults.update(overrides)
    publisher = Publisher(**defaults)  # ty: ignore[invalid-argument-type]
    db.add(publisher)
    db.commit()
    db.refresh(publisher)
    return publisher


def create_random_tag(db: Session, **overrides: object) -> Tag:
    name = random_lower_string()
    defaults: dict[str, object] = {
        "slug": slugify(name),
        "name": name,
        "description": random_lower_string(),
    }
    defaults.update(overrides)
    tag = Tag(**defaults)  # ty: ignore[invalid-argument-type]
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def create_random_article(db: Session, **overrides: object) -> Article:
    # every article needs a publisher; make one unless the caller supplied it
    if "publisher_id" not in overrides:
        overrides["publisher_id"] = create_random_publisher(db).id

    defaults: dict[str, object] = {
        "title": random_lower_string(),
        "url": f"https://example.com/{random_lower_string()}",
        "score": random.randint(1, 10),
        "summary": random_lower_string(),
        "kind": ArticleKind.post,
        "content": random_lower_string(),
    }
    defaults.update(overrides)
    article = Article(**defaults)  # ty: ignore[invalid-argument-type]
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def tag_article(db: Session, article: Article, tag: Tag) -> None:
    assert article.id is not None and tag.id is not None
    db.add(ArticleTag(article_id=article.id, tag_id=tag.id))
    db.commit()
