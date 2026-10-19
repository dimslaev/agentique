"""The stories rail endpoint."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.db.factories import (
    create_random_article,
    create_random_publisher,
    random_lower_string,
)
from app.core.settings import settings
from app.features.stories import service as stories


def test_the_route_serves_the_list(
    client: TestClient, db: Session, made: dict[str, list[int]]
) -> None:
    now = datetime.now(UTC)
    publishers = [create_random_publisher(db), create_random_publisher(db)]
    urls = []
    for i, publisher in enumerate([*publishers, publishers[0]]):
        article = create_random_article(
            db, publisher_id=publisher.id, published_at=now - timedelta(days=3 - i)
        )
        assert article.id is not None
        made["articles"].append(article.id)
        urls.append(article.url)
    made["publishers"] += [p.id for p in publishers if p.id is not None]
    slug = f"served-{random_lower_string()[:6]}"
    stories.save_story(db, slug, "Served", "What it is. Why now.", urls)

    r = client.get(f"{settings.API_V1_STR}/stories/", params={"limit": 20})
    assert r.status_code == 200
    story = next(s for s in r.json() if s["slug"] == slug)
    assert set(story["articles"][0]) == {
        "id",
        "title",
        "url",
        "publisher",
        "published_at",
        "score",
    }
