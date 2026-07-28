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
    categorize_article,
    create_random_article,
    create_random_category,
    create_random_publisher,
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
    "/categories",
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
    assert article["publisher"]["name"]
    assert article["publisher"]["slug"]
    assert isinstance(article["categories"], list)
    # score is gone: relevance is expressed by which categories claimed the
    # article, not by a number
    assert "score" not in article
    # the old flat source columns must not leak back into the response
    assert "source" not in article
    assert "source_type" not in article


def test_read_articles_filter_category(auth_client: TestClient, db: Session) -> None:
    """One category, newest first — this is exactly a homepage lane."""
    now = datetime.now(UTC)
    category = create_random_category(db)
    inside = create_random_article(db, published_at=now)
    create_random_article(db, published_at=now)
    categorize_article(db, inside, category)

    r = auth_client.get(
        f"{ARTICLES_URL}/", params={"category": category.slug, "limit": 50}
    )
    assert r.status_code == 200
    data = r.json()
    assert [a["id"] for a in data["data"]] == [inside.id]
    assert data["count"] == 1
    assert [c["slug"] for c in data["data"][0]["categories"]] == [category.slug]


def test_read_articles_filter_unknown_category_returns_nothing(
    auth_client: TestClient,
) -> None:
    r = auth_client.get(
        f"{ARTICLES_URL}/", params={"category": "no-such-category", "limit": 50}
    )
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_read_articles_filter_kind(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/", params={"kind": "repo", "limit": 50})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] > 0
    assert all(a["kind"] == "repo" for a in data["data"])


def test_read_articles_filter_never_increases_count(auth_client: TestClient) -> None:
    base = auth_client.get(f"{ARTICLES_URL}/").json()["count"]
    filtered = auth_client.get(f"{ARTICLES_URL}/", params={"kind": "repo"}).json()[
        "count"
    ]
    assert filtered <= base


def test_read_articles_sort_published_at_desc(auth_client: TestClient) -> None:
    r = auth_client.get(
        f"{ARTICLES_URL}/", params={"sort": "published_at-desc", "limit": 50}
    )
    data = r.json()["data"]
    dates = [
        datetime.fromisoformat(a["published_at"])
        for a in data
        if a["published_at"] is not None
    ]
    assert dates == sorted(dates, reverse=True)


def test_read_articles_sort_default_is_published_at_desc(
    auth_client: TestClient,
) -> None:
    """With score gone, newest-first is the only sensible default — and it is
    what every homepage lane asks for anyway."""
    r = auth_client.get(f"{ARTICLES_URL}/", params={"limit": 50})
    dates = [a["published_at"] for a in r.json()["data"] if a["published_at"]]
    assert dates == sorted(dates, reverse=True)


def test_articles_without_a_published_date_sort_last(
    auth_client: TestClient, db: Session
) -> None:
    """Postgres sorts NULLs FIRST on a DESC order, and `parse_date` returns None
    whenever a feed omits or malforms its pubDate. Now that newest-first is the
    default sort, one undated article would otherwise sit at the top of the feed
    and of every homepage lane forever."""
    undated = create_random_article(db, published_at=None)
    dated = create_random_article(db, published_at=datetime.now(UTC))

    ids = [
        a["id"]
        for a in auth_client.get(f"{ARTICLES_URL}/", params={"limit": 50}).json()[
            "data"
        ]
    ]
    assert dated.id in ids
    if undated.id in ids:
        assert ids.index(dated.id) < ids.index(undated.id)
    assert ids[0] != undated.id


def test_read_articles_since_narrows_results(auth_client: TestClient) -> None:
    wide_since = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    narrow_since = (datetime.now(UTC) - timedelta(days=3)).isoformat()

    wide = auth_client.get(
        f"{ARTICLES_URL}/", params={"since": wide_since, "limit": 50}
    ).json()
    narrow = auth_client.get(
        f"{ARTICLES_URL}/", params={"since": narrow_since, "limit": 50}
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


def test_read_articles_q_filters_title_or_content(
    auth_client: TestClient, db: Session
) -> None:
    now = datetime.now(UTC)
    # Unique per run: a literal marker also matches the rows this test left
    # behind on a previous run against the same database.
    marker = f"zzqq{uuid.uuid4().hex[:12]}"
    by_title = create_random_article(db, title=f"A {marker} headline", published_at=now)
    by_content = create_random_article(
        db, content=f"body mentions {marker} here", published_at=now
    )
    create_random_article(db, published_at=now)

    r = auth_client.get(f"{ARTICLES_URL}/", params={"q": marker, "limit": 50})
    assert r.status_code == 200
    ids = {a["id"] for a in r.json()["data"]}
    assert ids == {by_title.id, by_content.id}


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
    assert isinstance(data["categories"], list)
    assert len(data["publishers"]) > 0
    assert len(data["categories"]) > 0
    for p in data["publishers"]:
        assert p["count"] >= 1
    publisher_counts = [p["count"] for p in data["publishers"]]
    assert publisher_counts == sorted(publisher_counts, reverse=True)
    # Unlike publishers, category counts are NOT sorted descending — the list
    # comes back in fixed lane order, because the category list is the site's
    # editorial shape and must not reshuffle as articles arrive.
    slugs = [c["slug"] for c in data["categories"]]
    assert len(slugs) == len(set(slugs))


def test_article_facets_respects_limit(auth_client: TestClient) -> None:
    r = auth_client.get(f"{ARTICLES_URL}/facets", params={"limit": 2})
    assert r.status_code == 200
    data = r.json()
    assert len(data["publishers"]) <= 2
    assert len(data["categories"]) <= 2


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


def test_search_categories(auth_client: TestClient, db: Session) -> None:
    category = create_random_category(db, name="Zzz Unique Category")
    article = create_random_article(db)
    categorize_article(db, article, category)

    r = auth_client.get(f"{ARTICLES_URL}/categories", params={"q": "unique"})
    assert r.status_code == 200
    data = r.json()
    found = next((c for c in data if c["slug"] == category.slug), None)
    assert found is not None
    assert found["count"] == 1


def test_search_categories_no_match(auth_client: TestClient) -> None:
    r = auth_client.get(
        f"{ARTICLES_URL}/categories", params={"q": "no-such-category-xyz"}
    )
    assert r.status_code == 200
    assert r.json() == []


def test_category_facets_include_empty_categories(
    auth_client: TestClient, db: Session
) -> None:
    """A lane with nothing in it yet is information, not something to hide."""
    category = create_random_category(db, name="Zzz Empty Category")

    r = auth_client.get(f"{ARTICLES_URL}/categories", params={"limit": 50})
    assert r.status_code == 200
    found = next((c for c in r.json() if c["slug"] == category.slug), None)
    assert found is not None
    assert found["count"] == 0


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
    liked = create_random_article(db, published_at=now)
    unliked = create_random_article(db, published_at=now)

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
    # Ties now fall back to published_at desc, so give them distinct times.
    older_more_likes = create_random_article(db, published_at=now - timedelta(hours=3))
    newer_no_likes = create_random_article(db, published_at=now - timedelta(hours=1))
    tied_a = create_random_article(db, published_at=now - timedelta(hours=2))

    headers_list = [
        authentication_token_from_email(client=client, email=random_email(), db=db)
        for _ in range(2)
    ]
    for headers in headers_list:
        client.put(f"{ARTICLES_URL}/{older_more_likes.id}/like", headers=headers)
    client.put(f"{ARTICLES_URL}/{tied_a.id}/like", headers=headers_list[0])

    r = client.get(
        f"{ARTICLES_URL}/",
        params={"sort": "likes-desc", "limit": 50, "since": RECENT_SINCE},
        headers=headers_list[0],
    )
    ids = [a["id"] for a in r.json()["data"]]

    # 2 likes beats 1 like beats 0, regardless of date
    assert ids.index(older_more_likes.id) < ids.index(tied_a.id)
    assert ids.index(tied_a.id) < ids.index(newer_no_likes.id)


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
