"""The known-URL filter against the real schema: a URL that is an article, a
pending candidate or a settled reject is never fetched and judged again."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlmodel import Session, col, delete

from app.core.db.factories import create_random_article, random_lower_string
from app.core.db.ledger import Reject, RejectStage
from app.core.db.publisher import Publisher
from app.features.collect.filter import filter_known_urls
from app.features.collect.model import RawItem

TAG = random_lower_string()[:8]


def _item(path: str) -> RawItem:
    return {
        "title": path,
        "url": f"https://{TAG}.example/{path}",
        "content": "",
        "published_date": None,
        "source": "Hacker News",
    }


@pytest.fixture
def known(db: Session) -> Generator[None]:
    article = create_random_article(db, url=_item("published")["url"])
    db.add_all(
        [
            Reject(url=_item("pending")["url"], stage=RejectStage.pending),
            Reject(url=_item("rejected")["url"], stage=RejectStage.below_threshold),
        ]
    )
    db.commit()
    yield
    db.exec(delete(Reject).where(col(Reject.url).contains(TAG)))
    publisher_id = article.publisher_id
    db.delete(article)
    db.exec(delete(Publisher).where(col(Publisher.id) == publisher_id))
    db.commit()


@pytest.mark.usefixtures("known")
def test_only_unseen_urls_pass(db: Session) -> None:
    items = [_item(p) for p in ("published", "new", "pending", "rejected", "other")]
    fresh = filter_known_urls(db, items, "HN")
    assert [a["title"] for a in fresh] == ["new", "other"]


@pytest.mark.usefixtures("known")
def test_nothing_new_is_an_empty_list(db: Session) -> None:
    items = [_item(p) for p in ("published", "pending", "rejected")]
    assert filter_known_urls(db, items, "HN") == []


def test_no_items_reads_nothing(db: Session) -> None:
    assert filter_known_urls(db, [], "HN") == []
