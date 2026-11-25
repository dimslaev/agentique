"""The `add_publisher` tool: a new site gets the inactive publisher the nightly
run would make, a known one comes back unchanged, and a URL that names no
publisher is a tool error."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError
from sqlmodel import Session, col, select

from app.core.db.factories import random_lower_string
from app.core.db.publisher import (
    LinkPlatform,
    Publisher,
    PublisherKind,
    PublisherType,
)
from app.entry.mcp.add_publisher import add_publisher
from app.features.collect.model import RawItem


def _by_slug(db: Session, slug: str) -> Publisher:
    db.expire_all()
    return db.exec(select(Publisher).where(col(Publisher.slug) == slug)).one()


def test_a_new_site_gets_an_inactive_publisher_with_only_a_website_link(
    db: Session, made: dict[str, list[int]]
) -> None:
    host = f"{random_lower_string()}.example"
    result = add_publisher(f"https://{host}/posts/one", "AINews top story")

    slug = host.replace(".", "-")
    assert result == f"Added {slug} (unknown, inactive)"
    publisher = _by_slug(db, slug)
    assert publisher.id is not None
    made["publishers"].append(publisher.id)
    assert publisher.is_active is False
    assert publisher.kind == PublisherKind.unknown
    assert publisher.type == PublisherType.other
    assert publisher.links == {LinkPlatform.website: f"https://{host}"}


def test_a_site_we_carry_comes_back_as_it_is(
    db: Session, made: dict[str, list[int]]
) -> None:
    host = f"{random_lower_string()}.example"
    first = add_publisher(f"https://{host}/a", "AINews top story")
    again = add_publisher(f"https://{host}/b", "alignednews top story")

    slug = host.replace(".", "-")
    assert first.startswith("Added ")
    assert again == f"Already have {slug} (unknown, inactive)"
    publisher = _by_slug(db, slug)
    assert publisher.id is not None
    made["publishers"].append(publisher.id)
    assert len(db.exec(select(Publisher).where(col(Publisher.slug) == slug)).all()) == 1


def test_an_active_publisher_is_reported_active(
    db: Session, made: dict[str, list[int]]
) -> None:
    host = f"{random_lower_string()}.example"
    publisher = Publisher(
        slug=host.replace(".", "-"),
        name=host,
        kind=PublisherKind.lab,
        links={LinkPlatform.website: f"https://{host}"},
        is_active=True,
    )
    db.add(publisher)
    db.commit()
    assert publisher.id is not None
    made["publishers"].append(publisher.id)

    result = add_publisher(f"https://blog.{host}/post", "AINews top story")
    assert result == f"Already have {publisher.slug} (lab, active)"


@pytest.mark.parametrize("reason", ["", "   "])
def test_a_blank_reason_is_refused(reason: str) -> None:
    with pytest.raises(ToolError, match="reason"):
        add_publisher("https://never-made.example/post", reason)


@pytest.mark.parametrize("url", ["", "not a url", "ftp://never-made.example/x"])
def test_a_url_that_is_not_http_is_refused(url: str) -> None:
    with pytest.raises(ToolError, match="not an http"):
        add_publisher(url, "AINews top story")


def test_a_shared_host_with_no_author_is_refused(db: Session) -> None:
    with pytest.raises(ToolError, match="names no publisher"):
        add_publisher("https://www.reddit.com/r/LocalLLaMA/comments/abc", "AINews")
    db.expire_all()
    assert (
        db.exec(select(Publisher).where(col(Publisher.slug) == "reddit-com")).first()
        is None
    )


def test_a_shortener_is_credited_to_where_it_lands(
    db: Session, made: dict[str, list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    host = f"{random_lower_string()}.example"

    def land(items: list[RawItem]) -> list[RawItem]:
        for item in items:
            item["url"] = f"https://{host}/posts/one?utm_source=ainews"
        return items

    monkeypatch.setattr("app.features.collect.submit.unwrap_redirects", land)
    result = add_publisher("https://bit.ly/never-made", "AINews top story")

    slug = host.replace(".", "-")
    assert result == f"Added {slug} (unknown, inactive)"
    publisher = _by_slug(db, slug)
    assert publisher.id is not None
    made["publishers"].append(publisher.id)


def test_an_event_page_makes_no_publisher(db: Session) -> None:
    with pytest.raises(ToolError, match="event or reference page"):
        add_publisher("https://luma.com/never-made-event", "AINews")
    db.expire_all()
    assert (
        db.exec(select(Publisher).where(col(Publisher.slug) == "luma-com")).first()
        is None
    )
