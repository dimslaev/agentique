from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pgvector.sqlalchemy import Vector
from sqlalchemy import cast
from sqlmodel import Session, select

from app.api.routes import articles
from app.core.config import settings
from app.models_agentique import Article

ARTICLES_URL = f"{settings.API_V1_STR}/articles"


def test_read_articles_default(client: TestClient) -> None:
    r = client.get(f"{ARTICLES_URL}/")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert len(data["data"]) > 0
    article = data["data"][0]
    assert "title" in article
    assert "score" in article


def test_read_articles_filter_category(client: TestClient) -> None:
    r = client.get(f"{ARTICLES_URL}/", params={"category": "dev", "limit": 50})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert all("dev" in a["categories"] for a in data["data"])


def test_read_articles_filter_min_score(client: TestClient) -> None:
    r = client.get(f"{ARTICLES_URL}/", params={"min_score": 8, "limit": 50})
    assert r.status_code == 200
    data = r.json()
    assert all(a["score"] >= 8 for a in data["data"])


def test_read_articles_filter_kind(client: TestClient) -> None:
    r = client.get(f"{ARTICLES_URL}/", params={"kind": "repo", "limit": 50})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert all(a["kind"] == "repo" for a in data["data"])


def test_read_articles_filter_never_increases_count(client: TestClient) -> None:
    base = client.get(f"{ARTICLES_URL}/").json()["count"]
    filtered = client.get(f"{ARTICLES_URL}/", params={"min_score": 5}).json()["count"]
    assert filtered <= base


def test_read_articles_sort_published_at_desc(client: TestClient) -> None:
    r = client.get(
        f"{ARTICLES_URL}/", params={"sort": "published_at-desc", "limit": 50}
    )
    data = r.json()["data"]
    dates = [datetime.fromisoformat(a["published_at"]) for a in data]
    assert dates == sorted(dates, reverse=True)


def test_read_articles_sort_default_is_score_desc(client: TestClient) -> None:
    r = client.get(f"{ARTICLES_URL}/", params={"limit": 50})
    scores = [a["score"] for a in r.json()["data"]]
    assert scores == sorted(scores, reverse=True)


def test_read_articles_since_narrows_results(client: TestClient) -> None:
    wide_since = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    narrow_since = (datetime.now(UTC) - timedelta(days=3)).isoformat()

    wide = client.get(
        f"{ARTICLES_URL}/", params={"since": wide_since, "limit": 50}
    ).json()
    narrow = client.get(
        f"{ARTICLES_URL}/", params={"since": narrow_since, "limit": 50}
    ).json()

    assert narrow["count"] <= wide["count"]
    narrow_ids = {a["id"] for a in narrow["data"]}
    wide_ids = {a["id"] for a in wide["data"]}
    assert narrow_ids <= wide_ids


def test_read_articles_malformed_since_falls_back_to_default_window(
    client: TestClient,
) -> None:
    default = client.get(f"{ARTICLES_URL}/").json()
    malformed = client.get(f"{ARTICLES_URL}/", params={"since": "not-a-date"}).json()

    assert malformed["count"] == default["count"]


def test_search_articles(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_vec = [0.05] * 256
    monkeypatch.setattr(articles, "_embed", lambda text: fake_vec)

    r = client.get(f"{ARTICLES_URL}/search", params={"q": "agents", "limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert len(data["data"]) <= 5
    assert data["count"] == len(data["data"])

    expected_ids = db.exec(
        select(Article.id)
        .where(Article.score.is_not(None))  # type: ignore[union-attr]
        .where(Article.embedding.is_not(None))  # type: ignore[union-attr]
        .order_by(cast(Article.embedding, Vector(256)).cosine_distance(fake_vec))
        .limit(5)
    ).all()
    assert [a["id"] for a in data["data"]] == list(expected_ids)


def test_article_stats(client: TestClient) -> None:
    r = client.get(f"{ARTICLES_URL}/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 50
    datetime.fromisoformat(data["lastUpdated"])
