"""Who an item is credited to, against the real schema: an aggregator's links
go to their authors, made on the spot when we have not seen the site."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlmodel import Session, col, delete, select

from app.core.db.factories import random_lower_string
from app.core.db.publisher import LinkPlatform, Publisher, PublisherKind, PublisherType
from app.features.collect import publishers as publishers_module
from app.features.collect.publishers import (
    PublisherResolver,
    feed_sources_from_db,
    lab_watch_targets_from_db,
    newsletter_senders_from_db,
)

TAG = random_lower_string()[:8]


@pytest.fixture
def sources(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> Generator[dict[str, Publisher]]:
    monkeypatch.setattr(publishers_module, "account_type", lambda owner: "User")
    made = {
        "aggregator": Publisher(
            name=f"{TAG} News",
            slug=f"{TAG}-news",
            kind=PublisherKind.community,
            type=PublisherType.hn,
            links={LinkPlatform.website: f"https://news.{TAG}.com"},
        ),
        "feed": Publisher(
            name=f"{TAG} Feed",
            slug=f"{TAG}-feed",
            kind=PublisherKind.company,
            type=PublisherType.rss,
            links={LinkPlatform.website: f"https://{TAG}-feed.com"},
        ),
    }
    db.add_all(made.values())
    db.commit()
    yield made
    db.exec(delete(Publisher).where(col(Publisher.slug).contains(TAG)))
    db.commit()


def test_an_aggregators_link_to_a_new_site_gets_a_publisher_of_its_own(
    db: Session, sources: dict[str, Publisher]
) -> None:
    resolver = PublisherResolver(db)
    url = f"https://blog.{TAG}.dev/a-post"

    publisher = resolver.publisher_for(url, sources["aggregator"].name)

    assert publisher.id not in (sources["aggregator"].id, sources["feed"].id)
    assert publisher.name == f"blog.{TAG}.dev"
    assert publisher.kind == PublisherKind.unknown
    # Never polled: inactive, and only a website link.
    assert publisher.is_active is False
    assert publisher.links == {"website": f"https://blog.{TAG}.dev"}
    # The next post on the site is credited to the same one, even in a new run.
    again = PublisherResolver(db).publisher_for(f"https://blog.{TAG}.dev/b", "x")
    assert again.id == publisher.id


def test_a_github_user_is_an_individual(
    db: Session, sources: dict[str, Publisher]
) -> None:
    resolver = PublisherResolver(db)
    url = f"https://github.com/{TAG}owner/repo"

    publisher = resolver.publisher_for(url, sources["aggregator"].name)

    assert (publisher.name, publisher.kind) == (f"{TAG}owner", PublisherKind.individual)
    assert (
        resolver.publisher_for(f"https://github.com/{TAG}owner/other", "x").id
        == publisher.id
    )


def test_the_aggregators_own_page_stays_with_it(
    db: Session, sources: dict[str, Publisher]
) -> None:
    resolver = PublisherResolver(db)
    url = f"https://news.{TAG}.com/item?id=1"
    assert (
        resolver.publisher_for(url, sources["aggregator"].name).id
        == sources["aggregator"].id
    )


def test_a_shared_host_that_names_no_author_stays_with_the_aggregator(
    db: Session, sources: dict[str, Publisher]
) -> None:
    resolver = PublisherResolver(db)
    url = "https://x.com/someone/status/1"
    assert (
        resolver.publisher_for(url, sources["aggregator"].name).id
        == sources["aggregator"].id
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://old.reddit.com/r/LocalLLaMA/comments/abc/a_thread/",
        "https://m.youtube.com/watch?v=abc",
        "https://youtu.be/abc",
        "https://mobile.twitter.com/someone/status/1",
    ],
)
def test_a_shared_platforms_subdomain_names_no_author_either(
    db: Session, sources: dict[str, Publisher], url: str
) -> None:
    """A platform's subdomain is the platform, not a site of its own, so no
    publisher is made for it."""
    resolver = PublisherResolver(db)
    assert (
        resolver.publisher_for(url, sources["aggregator"].name).id
        == sources["aggregator"].id
    )
    assert resolver.created == []


def test_a_feeds_own_item_stays_with_the_feed(
    db: Session, sources: dict[str, Publisher]
) -> None:
    """A feed's posts may live on a host its links do not name; that is not a
    new author."""
    resolver = PublisherResolver(db)
    url = f"https://cdn.{TAG}-elsewhere.com/post"
    assert resolver.publisher_for(url, sources["feed"].name).id == sources["feed"].id


@pytest.mark.usefixtures("sources")
def test_an_unknown_source_is_quarantined_once(db: Session) -> None:
    """A source name the db has never seen gets one inactive publisher, and a
    second item from it in the same run reuses it."""
    resolver = PublisherResolver(db)
    name = f"{TAG} Brand New Feed"

    first = resolver.resolve(name)
    second = resolver.resolve(name)

    assert first is second
    assert (first.slug, first.is_active) == (f"{TAG}-brand-new-feed", False)
    assert resolver.quarantined == [first.slug]
    rows = db.exec(select(Publisher).where(Publisher.slug == first.slug)).all()
    assert len(rows) == 1


def test_a_new_author_never_takes_a_slug_already_in_use(
    db: Session, sources: dict[str, Publisher]
) -> None:
    """A GitHub owner can share a name with a publisher we already carry."""
    db.add(Publisher(name="taken", slug=f"{TAG}owner", kind=PublisherKind.media))
    db.commit()
    resolver = PublisherResolver(db)

    publisher = resolver.publisher_for(
        f"https://github.com/{TAG}owner/repo", sources["aggregator"].name
    )

    assert publisher.slug == f"{TAG}owner-2"
    assert resolver.created == [f"github.com/{TAG}owner"]


def test_a_url_on_a_known_site_beats_the_feed_that_carried_it(
    db: Session, sources: dict[str, Publisher]
) -> None:
    """Credit by URL comes first, whichever source found the item."""
    resolver = PublisherResolver(db)
    url = f"https://blog.{TAG}-feed.com/a-guest-post"
    assert (
        resolver.publisher_for(url, sources["aggregator"].name).id == sources["feed"].id
    )


@pytest.fixture
def polled(db: Session) -> Generator[dict[str, Publisher]]:
    """Active publishers with each kind of pollable link, and one switched off."""

    def pub(name: str, active: bool = True, **links: str) -> Publisher:
        return Publisher(
            name=f"{TAG} {name}",
            slug=f"{TAG}-{name}",
            kind=PublisherKind.media,
            is_active=active,
            links={LinkPlatform(k): v for k, v in links.items()},
        )

    made = {
        "both": pub(
            "both",
            rss=f"https://{TAG}-both.com/feed.xml",
            substack=f"https://{TAG}both.substack.com",
        ),
        "substack": pub("substack", substack=f"https://{TAG}stack.substack.com"),
        "lab": pub("lab", search=f"{TAG}-lab.ai"),
        "letter": pub("letter", email=f"@{TAG}-letter.com"),
        "off": pub(
            "off",
            active=False,
            rss=f"https://{TAG}-off.com/feed.xml",
            search=f"{TAG}-off.ai",
            email=f"@{TAG}-off.com",
        ),
    }
    db.add_all(made.values())
    db.commit()
    yield made
    db.exec(delete(Publisher).where(col(Publisher.slug).contains(TAG)))
    db.commit()


@pytest.mark.usefixtures("polled")
def test_feeds_come_from_active_publishers_preferring_rss(db: Session) -> None:
    feeds = [f for f in feed_sources_from_db(db) if f["name"].startswith(TAG)]
    assert sorted(feeds, key=lambda f: f["name"]) == [
        {"name": f"{TAG} both", "rssUrl": f"https://{TAG}-both.com/feed.xml"},
        {"name": f"{TAG} substack", "rssUrl": f"https://{TAG}stack.substack.com/feed"},
    ]


@pytest.mark.usefixtures("polled")
def test_lab_watch_targets_come_from_active_search_links(db: Session) -> None:
    targets = [t for t in lab_watch_targets_from_db(db) if t[0].startswith(TAG)]
    assert targets == [(f"{TAG} lab", f"{TAG}-lab.ai")]


@pytest.mark.usefixtures("polled")
def test_newsletter_senders_come_from_active_email_links(db: Session) -> None:
    senders = [s for s in newsletter_senders_from_db(db) if s[1].startswith(TAG)]
    assert senders == [(f"@{TAG}-letter.com", f"{TAG} letter")]
