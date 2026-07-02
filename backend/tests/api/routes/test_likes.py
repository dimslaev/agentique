from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.models_agentique import ArticleLike
from tests.utils.article import create_random_article
from tests.utils.user import create_random_user


def test_article_like_duplicate_pk_raises(db: Session) -> None:
    user = create_random_user(db)
    article = create_random_article(db)
    assert user.id is not None
    assert article.id is not None

    db.add(ArticleLike(user_id=user.id, article_id=article.id))
    db.commit()

    db.add(ArticleLike(user_id=user.id, article_id=article.id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_article_like_created_at_auto_populates(db: Session) -> None:
    user = create_random_user(db)
    article = create_random_article(db)
    assert user.id is not None
    assert article.id is not None

    like = ArticleLike(user_id=user.id, article_id=article.id)
    db.add(like)
    db.commit()
    db.refresh(like)

    assert isinstance(like.created_at, datetime)
