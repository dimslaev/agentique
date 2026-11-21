"""The newsletter's reads against the real schema: the week's articles, most
liked first, and `liked` reaching an article older than the week."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, col, delete

from app.core.db.article import Article
from app.core.db.factories import create_random_user, random_lower_string
from app.core.db.like import ArticleLike
from app.core.db.publisher import Publisher, PublisherKind, PublisherType
from app.features.newsletter import service as digest

TAG = random_lower_string()[:8]


@pytest.fixture
def world(db: Session) -> Generator[dict[str, str]]:
    publisher = Publisher(
        name=f"{TAG} Ollama",
        slug=f"{TAG}-ollama",
        kind=PublisherKind.company,
        type=PublisherType.rss,
    )
    db.add(publisher)
    db.commit()
    now = datetime.now(UTC)

    def article(
        name: str,
        score: int,
        created_at: datetime = now,
        marked_for_deletion_at: datetime | None = None,
    ) -> Article:
        url = f"https://ollama.example/{TAG}/{name}"
        return Article(
            title=f"{TAG} {name}",
            url=url,
            publisher_id=publisher.id or 0,
            score=score,
            summary=f"summary of {url}",
            created_at=created_at,
            marked_for_deletion_at=marked_for_deletion_at,
        )

    made = {
        "liked": article("liked", 60),
        "top": article("top", 92),
        "low": article("low", 40),
        "ancient": article("ancient", 90, created_at=now - timedelta(days=40)),
        "marked": article("marked", 95, marked_for_deletion_at=now),
    }
    db.add_all(made.values())
    db.commit()
    user = create_random_user(db)
    for name in ("liked", "ancient"):
        db.add(ArticleLike(user_id=user.id, article_id=made[name].id or 0))
    db.commit()

    yield {name: a.url for name, a in made.items()}

    db.exec(delete(ArticleLike).where(col(ArticleLike.user_id) == user.id))
    db.exec(delete(Article).where(col(Article.url).contains(TAG)))
    db.delete(publisher)
    db.delete(user)
    db.commit()


def test_week_lists_this_weeks_articles_most_liked_first(
    db: Session, world: dict[str, str]
) -> None:
    week = [a for a in digest.get_last_week_articles(db) if TAG in a["url"]]
    assert [a["url"] for a in week] == [world["liked"], world["top"], world["low"]]
    assert week[0]["likes"] == 1
    assert week[0]["publisher_kind"] == "company"
    assert week[0]["summary"] == f"summary of {world['liked']}"


def test_liked_reaches_an_article_older_than_the_week(
    db: Session, world: dict[str, str]
) -> None:
    liked = {a["url"]: a for a in digest.liked(db) if TAG in a["url"]}
    assert set(liked) == {world["liked"], world["ancient"]}
    assert liked[world["ancient"]]["likes"] == 1
