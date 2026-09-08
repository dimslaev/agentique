"""Tests for article listing, search, and facet endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pgvector.sqlalchemy import Vector
from sqlalchemy import cast
from sqlmodel import Session, col, select

from app import crud
from app.api.routes import articles
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.models import Article
from tests.utils.article import (
    create_random_article,
    create_random_publisher,
    create_random_tag,
    tag_article,
)
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import random_email

ARTICLES_URL = f"{settings.API_V1_STR}/articles"

# A recent `since`, for tests that want a narrow window.
RECENT_SINCE = (datetime.now(UTC) - timedelta(days=1)).isoformat()


@pytest.fixture(scope="module")
def reader_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    """Headers for an ordinary logged-in reader."""
    email = random_email()
    headers = authentication_token_from_email(client=client, email=email, db=db)
    assert crud.get_user_by_email(session=db, email=email) is not None
    return headers


@pytest.fixture(scope="module")
def auth_client(
    reader_token_headers: dict[str, str],
) -> Generator[TestClient]:
    """A TestClient that sends a logged-in reader's bearer token on every request.

    Reads are public; the token only decides whether `liked_by_me` is filled in.
    """
    with TestClient(app) as c:
        c.headers.update(reader_token_headers)
        yield c


# --- public reads ------------------------------------------------------------

READ_ENDPOINTS = [
    "/",
    "/search?q=agents",
    "/facets",
    "/publishers",
    "/tags",
    "/stats",
]


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_read_endpoints_are_public(client: TestClient, path: str) -> None:
    r = client.get(f"{ARTICLES_URL}{path}")
    assert r.status_code == 200


def test_read_articles_anonymous_has_no_likes(client: TestClient) -> None:
    r = client.get(f"{ARTICLES_URL}/", params={"limit": 5})
    assert r.status_code == 200
    assert all(a["liked_by_me"] is False for a in r.json()["data"])


def test_read_articles_garbage_token_falls_back_to_anonymous(
    client: TestClient,
) -> None:
    r = client.get(
        f"{ARTICLES_URL}/",
        params={"limit": 5},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert r.status_code == 200


def test_read_articles_valid_token_unknown_user_is_anonymous(
    client: TestClient,
) -> None:
    token = create_access_token(str(uuid.uuid4()), expires_delta=timedelta(minutes=5))
    r = client.get(
        f"{ARTICLES_URL}/",
        params={"limit": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert all(a["liked_by_me"] is False for a in r.json()["data"])


# --- reads -------------------------------------------------------------------


def test_read_articles_default(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert len(data["data"]) > 0
    article = data["data"][0]
    assert "title" in article
    assert "score" in article
    assert article["publisher"]["name"]
    assert article["publisher"]["slug"]
    assert isinstance(article["tags"], list)
    # the old flat source columns must not leak back into the response
    assert "source" not in article
    assert "source_type" not in article


def test_read_articles_filter_category(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/", params={"category": "dev", "limit": 50})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert all("dev" in a["categories"] for a in data["data"])


def test_read_articles_filter_min_score(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/", params={"min_score": 8, "limit": 50})
    assert r.status_code == 200
    data = r.json()
    assert all(a["score"] >= 8 for a in data["data"])


def test_read_articles_filter_kind(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/", params={"kind": "repo", "limit": 50})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert all(a["kind"] == "repo" for a in data["data"])


def test_read_articles_filter_tag(auth_client: TestClient, db: Session) -> None:
    now = datetime.now(UTC)
    tag = create_random_tag(db)
    tagged = create_random_article(db, published_at=now)
    create_random_article(db, published_at=now)
    tag_article(db, tagged, tag)

    r = auth_client.get(f"{ARTICLES_URL}/", params={"tag": tag.slug, "limit": 50})
    assert r.status_code == 200
    data = r.json()
    assert [a["id"] for a in data["data"]] == [tagged.id]
    assert data["count"] == 1
    assert [t["slug"] for t in data["data"][0]["tags"]] == [tag.slug]


def test_read_articles_filter_unknown_tag_returns_nothing(
    auth_client: TestClient,
) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/", params={"tag": "no-such-tag", "limit": 50})
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_read_articles_filter_never_increases_count(auth_client: TestClient) -> None:
    base = auth_client.get(f"{ARTICLES_URL}/").json()["count"]
    filtered = auth_client.get(f"{ARTICLES_URL}/", params={"min_score": 5}).json()[
        "count"
    ]
    assert filtered <= base


def test_read_articles_sort_published_at_desc(auth_client: TestClient) -> None:
    r = auth_client.get(
        f"{ARTICLES_URL}/", params={"sort": "published_at-desc", "limit": 50}
    )
    data = r.json()["data"]
    dates = [datetime.fromisoformat(a["published_at"]) for a in data]
    assert dates == sorted(dates, reverse=True)


def test_read_articles_sort_default_is_score_desc(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/", params={"limit": 50})
    scores = [a["score"] for a in r.json()["data"]]
    assert scores == sorted(scores, reverse=True)


def test_read_articles_since_narrows_results(auth_client: TestClient) -> None:
    wide_since = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    narrow_since = (datetime.now(UTC) - timedelta(days=3)).isoformat()

    # sort by published_at (not the default score-desc): only then is a
    # narrower window's page mathematically guaranteed to be a subset of a
    # wider window's page, regardless of how scores are distributed.
    wide = auth_client.get(
        f"{ARTICLES_URL}/",
        params={"since": wide_since, "limit": 50, "sort": "published_at-desc"},
    ).json()
    narrow = auth_client.get(
        f"{ARTICLES_URL}/",
        params={"since": narrow_since, "limit": 50, "sort": "published_at-desc"},
    ).json()

    assert narrow["count"] <= wide["count"]
    narrow_ids = {a["id"] for a in narrow["data"]}
    wide_ids = {a["id"] for a in wide["data"]}
    assert narrow_ids <= wide_ids


def test_read_articles_malformed_since_returns_422(
    auth_client: TestClient,
) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/", params={"since": "not-a-date"})
    assert r.status_code == 422


# --- unbounded history -------------------------------------------------------


def test_read_articles_missing_since_returns_all_time(client: TestClient) -> None:
    r = client.get(f"{ARTICLES_URL}/")
    assert r.status_code == 200
    assert r.json()["count"] > 0


def test_read_articles_old_since_ok_anonymous(client: TestClient) -> None:
    old_since = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    r = client.get(f"{ARTICLES_URL}/", params={"since": old_since})
    assert r.status_code == 200


def test_read_articles_old_since_ok_logged_in(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    old_since = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    r = client.get(
        f"{ARTICLES_URL}/",
        params={"since": old_since},
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200


def test_search_is_unbounded_for_anonymous(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_vec = [0.05] * 256
    monkeypatch.setattr(articles, "_embed", lambda text: fake_vec)
    now = datetime.now(UTC)
    # identical embedding to the query -> cosine distance 0 -> ranks first
    old = create_random_article(
        db, published_at=now - timedelta(days=20), embedding=fake_vec
    )
    recent = create_random_article(db, published_at=now, embedding=fake_vec)

    r = client.get(f"{ARTICLES_URL}/search", params={"q": "x", "limit": 50})
    assert r.status_code == 200
    ids = {a["id"] for a in r.json()["data"]}
    assert old.id in ids
    assert recent.id in ids


# Placed after the count-sensitive tests above (which assume the seeded
# window fits under the default limit=50) since these insert extra articles.
def test_read_articles_filter_publisher(auth_client: TestClient, db: Session) -> None:
    now = datetime.now(UTC)
    publisher = create_random_publisher(db)
    matched = create_random_article(db, publisher_id=publisher.id, published_at=now)
    create_random_article(db, published_at=now)

    r = auth_client.get(
        f"{ARTICLES_URL}/", params={"publisher": publisher.slug, "limit": 50}
    )
    assert r.status_code == 200
    data = r.json()
    assert [a["id"] for a in data["data"]] == [matched.id]
    assert data["count"] == 1
    assert data["data"][0]["publisher"]["slug"] == publisher.slug


def test_read_articles_filter_unknown_publisher_returns_nothing(
    auth_client: TestClient,
) -> None:
    r = auth_client.get(
        f"{ARTICLES_URL}/", params={"publisher": "no-such-publisher", "limit": 50}
    )
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_search_articles(
    auth_client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_vec = [0.05] * 256
    monkeypatch.setattr(articles, "_embed", lambda text: fake_vec)

    r = auth_client.get(f"{ARTICLES_URL}/search", params={"q": "agents", "limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert len(data["data"]) <= 5
    assert data["count"] == len(data["data"])

    expected_ids = db.exec(
        select(Article.id)
        .where(Article.embedding.is_not(None))  # type: ignore[union-attr]
        .order_by(
            cast(Article.embedding, Vector(256)).cosine_distance(fake_vec),
            col(Article.id).desc(),
        )
        .limit(5)
    ).all()
    assert [a["id"] for a in data["data"]] == list(expected_ids)


def test_article_facets(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/facets")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["publishers"], list)
    assert isinstance(data["tags"], list)
    assert len(data["publishers"]) > 0
    assert len(data["tags"]) > 0
    for p in data["publishers"]:
        assert p["count"] >= 1
    for t in data["tags"]:
        assert t["count"] >= 1
    publisher_counts = [p["count"] for p in data["publishers"]]
    tag_counts = [t["count"] for t in data["tags"]]
    assert publisher_counts == sorted(publisher_counts, reverse=True)
    assert tag_counts == sorted(tag_counts, reverse=True)


def test_article_facets_respects_limit(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/facets", params={"limit": 2})
    assert r.status_code == 200
    data = r.json()
    assert len(data["publishers"]) <= 2
    assert len(data["tags"]) <= 2


def test_search_publishers(auth_client: TestClient, db: Session) -> None:
    publisher = create_random_publisher(db, name="Zzz Unique Publisher")
    create_random_article(db, publisher_id=publisher.id)

    r = auth_client.get(f"{ARTICLES_URL}/publishers", params={"q": "unique"})
    assert r.status_code == 200
    data = r.json()
    found = next((p for p in data if p["slug"] == publisher.slug), None)
    assert found is not None
    assert found["count"] == 1


def test_search_publishers_no_match(auth_client: TestClient) -> None:
    r = auth_client.get(
        f"{ARTICLES_URL}/publishers", params={"q": "no-such-publisher-xyz"}
    )
    assert r.status_code == 200
    assert r.json() == []


def test_search_tags(auth_client: TestClient, db: Session) -> None:
    tag = create_random_tag(db, name="Zzz Unique Tag")
    article = create_random_article(db)
    tag_article(db, article, tag)

    r = auth_client.get(f"{ARTICLES_URL}/tags", params={"q": "unique"})
    assert r.status_code == 200
    data = r.json()
    found = next((t for t in data if t["slug"] == tag.slug), None)
    assert found is not None
    assert found["count"] == 1


def test_search_tags_no_match(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/tags", params={"q": "no-such-tag-xyz"})
    assert r.status_code == 200
    assert r.json() == []


def test_article_stats(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 50
    datetime.fromisoformat(data["lastUpdated"])


def test_read_articles_has_like_count_and_liked_by_me(
    auth_client: TestClient,
) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/", params={"limit": 50})
    data = r.json()["data"]
    assert len(data) > 0
    for article in data:
        assert article["like_count"] >= 0
        assert isinstance(article["liked_by_me"], bool)


def test_read_articles_liked_by_me_true_only_for_liked(
    client: TestClient, db: Session, normal_user_token_headers: dict[str, str]
) -> None:
    now = datetime.now(UTC)
    liked = create_random_article(db, score=9, published_at=now)
    unliked = create_random_article(db, score=9, published_at=now)

    r = client.put(f"{ARTICLES_URL}/{liked.id}/like", headers=normal_user_token_headers)
    assert r.status_code == 200

    r = client.get(
        f"{ARTICLES_URL}/",
        params={"limit": 50, "since": RECENT_SINCE},
        headers=normal_user_token_headers,
    )
    data = {a["id"]: a for a in r.json()["data"]}
    assert data[liked.id]["liked_by_me"] is True
    assert data[liked.id]["like_count"] == 1
    assert data[unliked.id]["liked_by_me"] is False
    assert data[unliked.id]["like_count"] == 0


def test_read_articles_sort_likes_desc(client: TestClient, db: Session) -> None:
    now = datetime.now(UTC)
    low_score_more_likes = create_random_article(db, score=3, published_at=now)
    high_score_no_likes = create_random_article(db, score=9, published_at=now)
    tied_score_a = create_random_article(db, score=5, published_at=now)
    tied_score_b = create_random_article(db, score=5, published_at=now)

    headers_list = [
        authentication_token_from_email(client=client, email=random_email(), db=db)
        for _ in range(2)
    ]
    for headers in headers_list:
        client.put(f"{ARTICLES_URL}/{low_score_more_likes.id}/like", headers=headers)
    client.put(f"{ARTICLES_URL}/{tied_score_a.id}/like", headers=headers_list[0])

    r = client.get(
        f"{ARTICLES_URL}/",
        params={"sort": "likes-desc", "limit": 50, "since": RECENT_SINCE},
        headers=headers_list[0],
    )
    data = r.json()["data"]
    ids = [a["id"] for a in data]

    assert ids.index(low_score_more_likes.id) < ids.index(high_score_no_likes.id)
    # tied like counts (both 0) fall back to score desc
    assert ids.index(high_score_no_likes.id) < ids.index(tied_score_b.id)
    # tied_score_a has 1 like, tied_score_b has 0 -> a before b despite equal score
    assert ids.index(tied_score_a.id) < ids.index(tied_score_b.id)


def test_search_articles_has_like_count_and_liked_by_me(
    auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_vec = [0.05] * 256
    monkeypatch.setattr(articles, "_embed", lambda text: fake_vec)

    r = auth_client.get(f"{ARTICLES_URL}/search", params={"q": "agents", "limit": 5})
    assert r.status_code == 200
    for article in r.json()["data"]:
        assert "like_count" in article
        assert "liked_by_me" in article
