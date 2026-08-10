"""The curation agent's tool API.

The agent is non-deterministic, so these pin the things that must hold however
it behaves: a bad token gets nothing, a duplicate URL never becomes a second
article, an unknown tag or publisher fails loudly instead of being dropped, and
`sql_read` cannot write.
"""

import asyncio
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, delete, func, select

from app.api.routes import agent
from app.core.config import settings
from app.models import Article, ArticleTag, FeedItem, FeedItemStatus, Publisher, Tag
from tests.utils.article import (
    create_random_article,
    create_random_publisher,
    create_random_tag,
)
from tests.utils.utils import random_lower_string

AGENT_URL = f"{settings.API_V1_STR}/agent"
TOKEN = "test-agent-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}

FAKE_VEC = [0.05] * 256


@pytest.fixture(autouse=True)
def agent_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test in this module runs with the agent API enabled."""
    monkeypatch.setattr(settings, "AGENT_API_TOKEN", TOKEN)


@pytest.fixture(autouse=True)
def no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never download the real embedding model to write a test article."""
    monkeypatch.setattr(agent, "_embed", lambda text: FAKE_VEC)


@pytest.fixture(autouse=True)
def clean_feed_items(db: Session) -> Generator[None]:
    """The inbox endpoints count every row in a status, so each test starts on
    an empty table and leaves one behind."""
    db.execute(delete(FeedItem))
    db.commit()
    yield
    db.execute(delete(FeedItem))
    db.commit()


@pytest.fixture(autouse=True)
def clean_articles(db: Session) -> Generator[None]:
    """Take back every article this module writes.

    The other route tests assert on counts and on date ordering over whatever
    is in the table, so an article left behind here fails a test over there.
    """
    high_water = db.exec(select(func.max(Article.id))).one() or 0
    yield
    ids = db.exec(select(Article.id).where(col(Article.id) > high_water)).all()
    if ids:
        db.execute(delete(ArticleTag).where(col(ArticleTag.article_id).in_(ids)))
        db.execute(delete(Article).where(col(Article.id) > high_water))
        db.commit()


def make_feed_item(db: Session, **overrides: object) -> FeedItem:
    defaults: dict[str, object] = {
        "url": f"https://example.com/{random_lower_string()}",
        "title": random_lower_string(),
        "content": random_lower_string(),
        "published_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    item = FeedItem(**defaults)  # type: ignore[arg-type]
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# ─── auth ────────────────────────────────────────────────────────────────────

ENDPOINTS = [
    ("get", "/feed-items"),
    ("get", "/publishers"),
    ("get", "/tags"),
    ("post", "/sql"),
    ("post", "/fetch-url"),
    ("post", "/articles"),
    ("post", "/publishers"),
    ("post", "/tags"),
    ("post", "/feed-items/1/decision"),
]


def call(client: TestClient, method: str, path: str, **kwargs: object) -> object:
    if method == "post":
        kwargs.setdefault("json", {})
    return client.request(method.upper(), f"{AGENT_URL}{path}", **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_every_endpoint_needs_the_token(
    client: TestClient, method: str, path: str
) -> None:
    assert call(client, method, path).status_code == 401  # type: ignore[attr-defined]


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_a_wrong_token_is_rejected(client: TestClient, method: str, path: str) -> None:
    r = call(client, method, path, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401  # type: ignore[attr-defined]


def test_the_api_is_off_when_no_token_is_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deploy that forgot AGENT_API_TOKEN must serve 503, never an open
    write API."""
    monkeypatch.setattr(settings, "AGENT_API_TOKEN", None)
    r = client.get(f"{AGENT_URL}/tags", headers=AUTH)
    assert r.status_code == 503


# ─── list_feed_items ─────────────────────────────────────────────────────────


def test_lists_new_items_newest_first(client: TestClient, db: Session) -> None:
    now = datetime.now(UTC)
    old = make_feed_item(db, fetched_at=now - timedelta(hours=2))
    new = make_feed_item(db, fetched_at=now)

    r = client.get(f"{AGENT_URL}/feed-items", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert [i["id"] for i in data["data"]] == [new.id, old.id]
    assert data["count"] == 2


def test_count_is_the_whole_status_not_the_page(
    client: TestClient, db: Session
) -> None:
    """The agent works in batches, so it needs to know what is left behind
    the limit."""
    for _ in range(3):
        make_feed_item(db)

    r = client.get(f"{AGENT_URL}/feed-items", params={"limit": 1}, headers=AUTH)
    data = r.json()
    assert len(data["data"]) == 1
    assert data["count"] == 3


def test_decided_items_are_not_in_the_new_batch(
    client: TestClient, db: Session
) -> None:
    make_feed_item(db, status=FeedItemStatus.accepted)
    make_feed_item(db, status=FeedItemStatus.rejected)
    pending = make_feed_item(db)

    r = client.get(f"{AGENT_URL}/feed-items", headers=AUTH)
    assert [i["id"] for i in r.json()["data"]] == [pending.id]


def test_can_ask_for_a_decided_status(client: TestClient, db: Session) -> None:
    accepted = make_feed_item(db, status=FeedItemStatus.accepted)
    make_feed_item(db)

    r = client.get(
        f"{AGENT_URL}/feed-items", params={"status": "accepted"}, headers=AUTH
    )
    assert [i["id"] for i in r.json()["data"]] == [accepted.id]


def test_content_is_clipped_and_says_so(client: TestClient, db: Session) -> None:
    make_feed_item(db, content="x" * 5000)

    r = client.get(
        f"{AGENT_URL}/feed-items", params={"content_chars": 100}, headers=AUTH
    )
    item = r.json()["data"][0]
    assert len(item["content"]) == 100
    assert item["content_truncated"] is True


def test_untruncated_content_is_not_flagged(client: TestClient, db: Session) -> None:
    make_feed_item(db, content="short")

    r = client.get(f"{AGENT_URL}/feed-items", headers=AUTH)
    item = r.json()["data"][0]
    assert item["content"] == "short"
    assert item["content_truncated"] is False


def test_carrier_and_links_come_back(client: TestClient, db: Session) -> None:
    """An aggregator item is only useful with its outbound candidates and the
    name of whoever carried it."""
    publisher = create_random_publisher(db)
    links = [{"url": "https://hf.co/x", "host": "hf.co", "kind": "huggingface"}]
    make_feed_item(db, feed_publisher_id=publisher.id, links=links)

    r = client.get(f"{AGENT_URL}/feed-items", headers=AUTH)
    item = r.json()["data"][0]
    assert item["feed_publisher"] == publisher.name
    assert item["feed_publisher_id"] == publisher.id
    assert item["links"] == links


# ─── mark_feed_item ──────────────────────────────────────────────────────────


def test_marking_an_item_records_the_reason(client: TestClient, db: Session) -> None:
    item = make_feed_item(db)

    r = client.post(
        f"{AGENT_URL}/feed-items/{item.id}/decision",
        json={"status": "rejected", "decision": "crypto, out of scope"},
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    assert body["decision"] == "crypto, out of scope"

    db.refresh(item)
    assert item.status == FeedItemStatus.rejected
    assert item.decided_at is not None


def test_cannot_mark_an_item_back_to_new(client: TestClient, db: Session) -> None:
    item = make_feed_item(db)
    r = client.post(
        f"{AGENT_URL}/feed-items/{item.id}/decision",
        json={"status": "new", "decision": "undo"},
        headers=AUTH,
    )
    assert r.status_code == 422


def test_the_decision_echoes_the_carrier_back(client: TestClient, db: Session) -> None:
    publisher = create_random_publisher(db)
    item = make_feed_item(db, feed_publisher_id=publisher.id)

    r = client.post(
        f"{AGENT_URL}/feed-items/{item.id}/decision",
        json={"status": "accepted", "decision": "first-party release"},
        headers=AUTH,
    )
    assert r.json()["feed_publisher"] == publisher.name


def test_marking_a_missing_item_is_a_404(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/feed-items/999999/decision",
        json={"status": "accepted", "decision": "x"},
        headers=AUTH,
    )
    assert r.status_code == 404


# ─── publishers ──────────────────────────────────────────────────────────────


def test_lists_and_filters_publishers(client: TestClient, db: Session) -> None:
    publisher = create_random_publisher(db)

    r = client.get(
        f"{AGENT_URL}/publishers", params={"q": publisher.name}, headers=AUTH
    )
    assert r.status_code == 200
    assert [p["slug"] for p in r.json()] == [publisher.slug]


def test_upsert_creates_a_publisher(client: TestClient, db: Session) -> None:
    slug = f"lab-{random_lower_string()}"
    r = client.post(
        f"{AGENT_URL}/publishers",
        json={
            "slug": slug,
            "name": "Some Lab",
            "kind": "company",
            "trust": "high",
            "links": {"website": "https://somelab.ai"},
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["slug"] == slug

    stored = db.exec(select(Publisher).where(Publisher.slug == slug)).one()
    assert stored.name == "Some Lab"
    assert stored.trust == "high"


def test_upsert_updates_an_existing_publisher(client: TestClient, db: Session) -> None:
    publisher = create_random_publisher(db)

    r = client.post(
        f"{AGENT_URL}/publishers",
        json={"slug": publisher.slug, "name": "Renamed", "kind": "media"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["id"] == publisher.id

    db.refresh(publisher)
    assert publisher.name == "Renamed"


def test_an_attribution_only_publisher_has_no_feed_to_poll(
    client: TestClient, db: Session
) -> None:
    """Active with no rss/substack link: the pipeline never polls it, the
    article still gets the right byline."""
    slug = f"lab-{random_lower_string()}"
    r = client.post(
        f"{AGENT_URL}/publishers",
        json={"slug": slug, "name": "First Party", "kind": "company"},
        headers=AUTH,
    )
    assert r.status_code == 200
    stored = db.exec(select(Publisher).where(Publisher.slug == slug)).one()
    assert stored.is_active is True
    assert stored.links == {}


def test_publisher_slugs_are_normalised(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/publishers",
        json={"slug": "Some Lab!! AI", "name": "Some Lab", "kind": "company"},
        headers=AUTH,
    )
    assert r.json()["slug"] == "some-lab-ai"


def test_a_publisher_needs_a_usable_slug(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/publishers",
        json={"slug": "!!!", "name": "!!!", "kind": "company"},
        headers=AUTH,
    )
    assert r.status_code == 422


# ─── tags ────────────────────────────────────────────────────────────────────


def test_lists_the_vocabulary_with_its_descriptions(
    client: TestClient, db: Session
) -> None:
    tag = create_random_tag(db)

    r = client.get(f"{AGENT_URL}/tags", headers=AUTH)
    assert r.status_code == 200
    match = next(t for t in r.json() if t["slug"] == tag.slug)
    assert match["description"] == tag.description


def test_creates_a_tag(client: TestClient, db: Session) -> None:
    slug = f"tag-{random_lower_string()}"
    r = client.post(
        f"{AGENT_URL}/tags",
        json={"slug": slug, "name": "A Tag", "description": "when to use it"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert db.exec(select(Tag).where(Tag.slug == slug)).one().name == "A Tag"


def test_creating_a_tag_twice_is_a_conflict(client: TestClient, db: Session) -> None:
    tag = create_random_tag(db)
    r = client.post(
        f"{AGENT_URL}/tags", json={"slug": tag.slug, "name": "dupe"}, headers=AUTH
    )
    assert r.status_code == 409


def test_a_tag_needs_a_usable_slug(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/tags", json={"slug": "!!!", "name": "!!!"}, headers=AUTH
    )
    assert r.status_code == 422


# ─── sql_read ────────────────────────────────────────────────────────────────


def test_runs_a_select(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/sql",
        json={"query": "SELECT 1 AS one, 'x' AS letter"},
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["columns"] == ["one", "letter"]
    assert body["rows"] == [[1, "x"]]
    assert body["truncated"] is False


def test_a_with_query_is_a_read(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/sql",
        json={"query": "WITH x AS (SELECT 1 AS n) SELECT n FROM x"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["rows"] == [[1]]


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM article",
        "UPDATE article SET score = 1",
        "INSERT INTO tag (slug, name) VALUES ('x', 'x')",
        "DROP TABLE feed_item",
        "  ",
    ],
)
def test_writes_are_refused(client: TestClient, query: str) -> None:
    r = client.post(f"{AGENT_URL}/sql", json={"query": query}, headers=AUTH)
    assert r.status_code == 422


def test_a_write_smuggled_after_a_select_is_refused(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/sql",
        json={"query": "SELECT 1; DROP TABLE feed_item"},
        headers=AUTH,
    )
    assert r.status_code == 422


def test_a_read_only_transaction_blocks_a_write_that_parses_as_a_read(
    client: TestClient, db: Session
) -> None:
    """The statement gate is not the only defence: postgres itself refuses."""
    item = make_feed_item(db)
    r = client.post(
        f"{AGENT_URL}/sql",
        json={
            "query": "WITH w AS (DELETE FROM feed_item RETURNING id) SELECT * FROM w"
        },
        headers=AUTH,
    )
    assert r.status_code == 400
    assert db.get(FeedItem, item.id) is not None


def test_a_broken_query_returns_the_database_error(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/sql", json={"query": "SELECT * FROM no_such_table"}, headers=AUTH
    )
    assert r.status_code == 400
    assert "no_such_table" in r.json()["detail"]


def test_rows_are_capped_and_flagged(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/sql",
        json={"query": "SELECT generate_series(1, 100)", "limit": 5},
        headers=AUTH,
    )
    body = r.json()
    assert body["row_count"] == 5
    assert body["truncated"] is True


def test_a_column_json_cannot_carry_comes_back_as_text(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/sql", json={"query": "SELECT INTERVAL '1 day' AS d"}, headers=AUTH
    )
    assert r.status_code == 200
    assert isinstance(r.json()["rows"][0][0], str)


def test_timestamps_come_back_as_iso_strings(client: TestClient, db: Session) -> None:
    make_feed_item(db)
    r = client.post(
        f"{AGENT_URL}/sql",
        json={"query": "SELECT fetched_at FROM feed_item"},
        headers=AUTH,
    )
    assert r.status_code == 200
    assert datetime.fromisoformat(r.json()["rows"][0][0]) is not None


# ─── fetch_url ───────────────────────────────────────────────────────────────


def test_fetches_and_extracts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent, "fetch_and_extract", lambda url: "the article text")
    r = client.post(
        f"{AGENT_URL}/fetch-url", json={"url": "https://example.com/post"}, headers=AUTH
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["text"] == "the article text"
    assert body["chars"] == len("the article text")


def test_a_page_that_gives_no_text_is_an_answer_not_an_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent, "fetch_and_extract", lambda url: "")
    r = client.post(
        f"{AGENT_URL}/fetch-url", json={"url": "https://example.com/post"}, headers=AUTH
    )
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_long_text_is_truncated(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        agent, "fetch_and_extract", lambda url: "x" * (agent.MAX_FETCH_CHARS + 10)
    )
    r = client.post(
        f"{AGENT_URL}/fetch-url", json={"url": "https://example.com/post"}, headers=AUTH
    )
    body = r.json()
    assert len(body["text"]) == agent.MAX_FETCH_CHARS
    assert body["truncated"] is True


def test_a_saturated_fetcher_says_so_instead_of_queueing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """fetch_url shares a process with the site: when every slot is taken, the
    answer is 'retry', not a request parked behind a 20s proxy fetch."""
    monkeypatch.setattr(agent, "_fetch_slots", asyncio.Semaphore(0))
    monkeypatch.setattr(settings, "AGENT_FETCH_QUEUE_SECONDS", 0.01)

    r = client.post(
        f"{AGENT_URL}/fetch-url", json={"url": "https://example.com/post"}, headers=AUTH
    )
    assert r.status_code == 503


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "not a url",
        "http://localhost:8000/admin",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
    ],
)
def test_refuses_non_public_targets(client: TestClient, url: str) -> None:
    """The URLs the agent passes here came out of feed content, so they are
    attacker-influenced."""
    r = client.post(f"{AGENT_URL}/fetch-url", json={"url": url}, headers=AUTH)
    assert r.status_code == 422


# ─── create_article ──────────────────────────────────────────────────────────


def article_payload(publisher_slug: str, **overrides: object) -> dict:
    payload: dict[str, object] = {
        "url": f"https://example.com/{random_lower_string()}",
        "title": "A real title about inference",
        "publisher_slug": publisher_slug,
        "score": 82,
        "kind": "blog",
        "categories": ["dev"],
        "summary": "What it says.",
        "content": "The article text.",
    }
    payload.update(overrides)
    return payload


def test_creates_an_article_with_tags(client: TestClient, db: Session) -> None:
    publisher = create_random_publisher(db)
    tag = create_random_tag(db)

    r = client.post(
        f"{AGENT_URL}/articles",
        json=article_payload(publisher.slug, tags=[tag.slug]),
        headers=AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tags"] == [tag.slug]
    assert body["embedded"] is True

    article = db.get(Article, body["id"])
    assert article is not None
    assert article.publisher_id == publisher.id
    assert article.score == 82
    links = db.exec(
        select(ArticleTag).where(col(ArticleTag.article_id) == article.id)
    ).all()
    assert [link.tag_id for link in links] == [tag.id]


def test_a_duplicate_url_is_a_conflict(client: TestClient, db: Session) -> None:
    publisher = create_random_publisher(db)
    existing = create_random_article(db)

    r = client.post(
        f"{AGENT_URL}/articles",
        json=article_payload(publisher.slug, url=existing.url),
        headers=AUTH,
    )
    assert r.status_code == 409


@pytest.mark.parametrize("field", ["url", "title"])
def test_a_blank_url_or_title_is_rejected(
    client: TestClient, db: Session, field: str
) -> None:
    publisher = create_random_publisher(db)
    r = client.post(
        f"{AGENT_URL}/articles",
        json=article_payload(publisher.slug, **{field: "   "}),
        headers=AUTH,
    )
    assert r.status_code == 422


def test_an_unknown_publisher_is_rejected(client: TestClient) -> None:
    r = client.post(
        f"{AGENT_URL}/articles", json=article_payload("no-such-publisher"), headers=AUTH
    )
    assert r.status_code == 422


def test_an_unknown_tag_fails_loudly(client: TestClient, db: Session) -> None:
    """Silently dropping a typo'd slug loses the tag and hides the bug."""
    publisher = create_random_publisher(db)
    r = client.post(
        f"{AGENT_URL}/articles",
        json=article_payload(publisher.slug, tags=["no-such-tag"]),
        headers=AUTH,
    )
    assert r.status_code == 422
    assert "no-such-tag" in r.json()["detail"]


def test_too_many_tags_is_rejected(client: TestClient, db: Session) -> None:
    publisher = create_random_publisher(db)
    slugs = [create_random_tag(db).slug for _ in range(4)]
    r = client.post(
        f"{AGENT_URL}/articles",
        json=article_payload(publisher.slug, tags=slugs),
        headers=AUTH,
    )
    assert r.status_code == 422


@pytest.mark.parametrize("score", [0, 101])
def test_a_score_outside_the_scale_is_rejected(
    client: TestClient, db: Session, score: int
) -> None:
    publisher = create_random_publisher(db)
    r = client.post(
        f"{AGENT_URL}/articles",
        json=article_payload(publisher.slug, score=score),
        headers=AUTH,
    )
    assert r.status_code == 422


def test_a_missing_published_at_is_filled_in(client: TestClient, db: Session) -> None:
    """A null published_at drops the article out of every date-filtered read,
    which is most of the site."""
    publisher = create_random_publisher(db)
    r = client.post(
        f"{AGENT_URL}/articles", json=article_payload(publisher.slug), headers=AUTH
    )
    article = db.get(Article, r.json()["id"])
    assert article is not None and article.published_at is not None


def test_an_article_survives_the_embedder_failing(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Losing the vector costs search; losing the article costs the article."""

    def boom(_text: str) -> list[float]:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(agent, "_embed", boom)
    publisher = create_random_publisher(db)

    r = client.post(
        f"{AGENT_URL}/articles", json=article_payload(publisher.slug), headers=AUTH
    )
    assert r.status_code == 200
    assert r.json()["embedded"] is False
    assert db.get(Article, r.json()["id"]) is not None


def test_the_agent_never_sends_a_vector(client: TestClient, db: Session) -> None:
    """`embedding` is not part of the write contract — a caller cannot poison
    the vector space by hand."""
    publisher = create_random_publisher(db)
    r = client.post(
        f"{AGENT_URL}/articles",
        json=article_payload(publisher.slug, embedding=[1.0] * 256),
        headers=AUTH,
    )
    assert r.status_code == 200
    article = db.get(Article, r.json()["id"])
    assert article is not None
    assert article.embedding is not None
    assert [round(v, 4) for v in article.embedding] == FAKE_VEC


def test_the_created_article_is_readable_through_the_public_api(
    client: TestClient, db: Session
) -> None:
    """End of the loop: what the agent writes is what the site serves."""
    publisher = create_random_publisher(db)
    tag = create_random_tag(db)
    payload = article_payload(publisher.slug, tags=[tag.slug], score=91)

    created = client.post(f"{AGENT_URL}/articles", json=payload, headers=AUTH).json()

    r = client.get(
        f"{settings.API_V1_STR}/articles/",
        params={"publisher": publisher.slug, "min_score": 90, "limit": 50},
    )
    assert r.status_code == 200
    served = r.json()["data"]
    assert [a["id"] for a in served] == [created["id"]]
    assert [t["slug"] for t in served[0]["tags"]] == [tag.slug]


def test_min_score_accepts_the_whole_1_100_scale(client: TestClient) -> None:
    """Regression: this was `le=10`, so every realistic min_score was a 422."""
    r = client.get(f"{settings.API_V1_STR}/articles/", params={"min_score": 65})
    assert r.status_code == 200
