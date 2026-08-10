"""The agent's inbox: what lands in `feed_item`, and what never lands twice.

This is the whole of the pipeline's judgment under the agent-driven design, so
the rules worth pinning are the ones that decide whether the agent ever sees an
item at all.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, col, delete, func, select

from app.models import Article, FeedItem, FeedItemStatus
from pipeline.steps.inbox import prune_feed_items, record_feed_items
from tests.utils.article import create_random_article, create_random_publisher
from tests.utils.utils import random_lower_string


@pytest.fixture(autouse=True)
def clean_feed_items(db: Session) -> Generator[None]:
    db.execute(delete(FeedItem))
    db.commit()
    yield
    db.execute(delete(FeedItem))
    db.commit()


@pytest.fixture(autouse=True)
def clean_articles(db: Session) -> Generator[None]:
    """Take back the article the "already published" test writes — the route
    tests assert on counts and date ordering over whatever is in the table."""
    high_water = db.exec(select(func.max(Article.id))).one() or 0
    yield
    db.execute(delete(Article).where(col(Article.id) > high_water))
    db.commit()


def fetched(url: str, **extra: object) -> dict:
    return {
        "title": "A title",
        "url": url,
        "content": "Some content",
        "published_date": "Mon, 10 Aug 2026 09:00:00 +0000",
        "source": "Hacker News",
        **extra,
    }


def stored(db: Session, url: str) -> FeedItem | None:
    return db.exec(select(FeedItem).where(FeedItem.url == url)).first()


def test_records_an_item_as_new(db: Session) -> None:
    url = f"https://example.com/{random_lower_string()}"

    assert record_feed_items(db, [fetched(url)], "Hacker News") == 1

    item = stored(db, url)
    assert item is not None
    assert item.status == FeedItemStatus.new
    assert item.decision is None
    assert item.published_at is not None


def test_a_thin_item_is_stored_not_dropped(db: Session) -> None:
    """The LLM funnel drops contentless items; the inbox keeps them, because
    the agent decides whether a title alone is worth a fetch."""
    url = f"https://example.com/{random_lower_string()}"

    record_feed_items(db, [fetched(url, content="")], "Hacker News")

    item = stored(db, url)
    assert item is not None
    assert item.content is None


def test_the_carrier_is_recorded_not_the_author(db: Session) -> None:
    publisher = create_random_publisher(db)
    url = f"https://example.com/{random_lower_string()}"

    record_feed_items(db, [fetched(url, publisher_id=publisher.id)], "AI News")

    item = stored(db, url)
    assert item is not None and item.feed_publisher_id == publisher.id


def test_outbound_candidates_are_kept(db: Session) -> None:
    url = f"https://example.com/{random_lower_string()}"
    links = [{"url": "https://github.com/a/b", "host": "github.com", "kind": "github"}]

    record_feed_items(db, [fetched(url, links=links)], "AI News")

    item = stored(db, url)
    assert item is not None and item.links == links


def test_an_item_already_in_the_inbox_is_skipped(db: Session) -> None:
    url = f"https://example.com/{random_lower_string()}"
    record_feed_items(db, [fetched(url)], "Hacker News")

    assert record_feed_items(db, [fetched(url)], "Hacker News") == 0
    assert len(db.exec(select(FeedItem).where(FeedItem.url == url)).all()) == 1


def test_an_already_published_url_is_skipped(db: Session) -> None:
    """A story we already carry must not come back for re-triage."""
    article = create_random_article(db)

    assert record_feed_items(db, [fetched(article.url)], "Feeds") == 0
    assert stored(db, article.url) is None


def test_a_decided_item_is_never_re_added(db: Session) -> None:
    url = f"https://example.com/{random_lower_string()}"
    record_feed_items(db, [fetched(url)], "Hacker News")
    item = stored(db, url)
    assert item is not None
    item.status = FeedItemStatus.rejected
    db.add(item)
    db.commit()

    assert record_feed_items(db, [fetched(url)], "Hacker News") == 0


def test_one_url_twice_in_a_single_run_lands_once(db: Session) -> None:
    """Two sources can surface the same URL in one run — the unique index
    would abort the whole insert, so the dedup has to hold in-batch too."""
    url = f"https://example.com/{random_lower_string()}"

    assert record_feed_items(db, [fetched(url), fetched(url)], "Feeds") == 1


def test_an_item_with_no_url_is_skipped(db: Session) -> None:
    assert record_feed_items(db, [fetched("")], "Feeds") == 0


def test_nothing_fetched_is_not_an_error(db: Session) -> None:
    assert record_feed_items(db, [], "Feeds") == 0


def test_an_unparseable_date_stores_no_date_rather_than_dropping_the_item(
    db: Session,
) -> None:
    url = f"https://example.com/{random_lower_string()}"

    record_feed_items(db, [fetched(url, published_date="not a date")], "Feeds")

    item = stored(db, url)
    assert item is not None and item.published_at is None


# ─── pruning ────────────────────────────────────────────────────────────────


def test_prunes_items_past_the_retention_window(db: Session) -> None:
    old = FeedItem(
        url=f"https://example.com/{random_lower_string()}",
        title="old",
        fetched_at=datetime.now(UTC) - timedelta(days=45),
    )
    recent = FeedItem(
        url=f"https://example.com/{random_lower_string()}", title="recent"
    )
    db.add(old)
    db.add(recent)
    db.commit()
    old_url, recent_url = old.url, recent.url

    assert prune_feed_items(db, days=30) == 1
    assert stored(db, recent_url) is not None
    assert stored(db, old_url) is None
