"""Source discovery against the real schema, with the network stubbed: the pool
it picks, what a feed's entries are marked with, and what a switch writes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, col, delete

from app.core.db.factories import (
    create_random_article,
    create_random_publisher,
    random_lower_string,
)
from app.core.db.ledger import Reject, RejectStage
from app.core.db.publisher import Publisher, PublisherKind, PublisherType
from app.features.curation import sources
from app.features.curation.model import SourceError

NOW = datetime.now(UTC)
TAG = random_lower_string()[:8]


def _rss(*posts: tuple[str, datetime]) -> bytes:
    items = "".join(
        f"<item><title>{u}</title><link>{u}</link>"
        f"<pubDate>{d.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate></item>"
        for u, d in posts
    )
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{items}</channel></rss>'.encode()


def _publisher(db: Session, made: dict[str, list[int]], **kw: object) -> Publisher:
    slug = f"{TAG}-{random_lower_string()[:6]}"
    fields: dict[str, object] = {
        "slug": slug,
        "kind": PublisherKind.individual,
        "is_active": False,
        "links": {"website": f"https://{slug}.dev"},
    }
    p = create_random_publisher(db, **(fields | kw))
    assert p.id is not None
    made["publishers"].append(p.id)
    return p


def test_the_pool_takes_proven_reopened_sites_and_culls_dead_feeds(
    db: Session, made: dict[str, list[int]]
) -> None:
    strong = _publisher(db, made)
    weak = _publisher(db, made)
    firehose = _publisher(db, made)
    untried = _publisher(db, made)
    off = _publisher(db, made, disabled_reason="probe 1/10", switched_at=NOW)
    back = _publisher(
        db,
        made,
        disabled_reason="probe 1/10",
        switched_at=NOW - timedelta(days=30),
    )
    a = create_random_article(db, publisher_id=back.id)
    assert a.id is not None
    made["articles"].append(a.id)
    noisy = _publisher(
        db, made, is_active=True, links={"rss": "https://n.dev/feed"}, last_new_at=NOW
    )
    quiet = _publisher(
        db,
        made,
        is_active=True,
        links={"rss": "https://q.dev/feed"},
        last_new_at=NOW - timedelta(days=200),
    )
    fresh = _publisher(
        db,
        made,
        is_active=True,
        links={"rss": "https://f.dev/feed"},
        switched_at=NOW - timedelta(days=1),
    )
    aggregator = _publisher(
        db,
        made,
        is_active=True,
        type=PublisherType.ainews,
        links={"rss": "https://a.dev/feed"},
        last_new_at=NOW,
    )
    counts = {
        aggregator.id: (0, 40),
        strong.id: (4, 1),
        weak.id: (1, 0),
        firehose.id: (20, 60),
        off.id: (2, 0),
        back.id: (2, 1),
        noisy.id: (0, 12),
        quiet.id: (3, 1),
        fresh.id: (0, 0),
    }

    found = sources.review_publishers(db, counts, 1000, NOW)  # type: ignore[arg-type]

    probe = [r["slug"] for r in found["probe"] if r["slug"].startswith(TAG)]
    assert probe == [strong.slug, back.slug, weak.slug]
    assert untried.slug not in probe
    culled = {r["slug"]: r["reason"] for r in found["deactivate"]}
    assert culled[noisy.slug].startswith("culled 0/12 90d")
    assert culled[quiet.slug].startswith("culled silent since")
    assert fresh.slug not in culled
    assert aggregator.slug not in culled


def test_find_feed_marks_what_agentique_already_decided(
    db: Session, made: dict[str, list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    p = _publisher(db, made)
    seen = create_random_article(db, publisher_id=p.id)
    assert seen.id is not None
    made["articles"].append(seen.id)
    turned_down = f"https://{TAG}.dev/no"
    db.add(Reject(url=turned_down, stage=RejectStage.below_threshold))
    db.commit()
    fresh = f"https://{TAG}.dev/new"
    feed = _rss(
        (seen.url, NOW - timedelta(days=3)),
        (fresh, NOW - timedelta(days=1)),
        (turned_down, NOW - timedelta(days=2)),
    )
    site = f"https://{TAG}.dev/"
    pages = {
        site: b'<link rel="alternate" type="application/rss+xml" href="/x.xml">',
        f"{site}x.xml": feed,
    }
    monkeypatch.setattr(sources, "_get", lambda u: pages.get(u, b""))
    try:
        found = sources.find_feed(db, site)
    finally:
        db.exec(delete(Reject).where(col(Reject.url) == turned_down))
        db.commit()

    assert found is not None
    assert found["feed_url"] == f"{site}x.xml"
    assert [(e["link"], e["judged"]) for e in found["entries"]] == [  # type: ignore[attr-defined]
        (fresh, ""),
        (turned_down, "below_threshold"),
        (seen.url, "approved"),
    ]
    monkeypatch.setattr(sources, "_get", lambda u: b"")
    assert sources.find_feed(db, site) is None
    empty = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'
    monkeypatch.setattr(sources, "_get", lambda u: empty if u == site else b"")
    assert sources.find_feed(db, site) == {"feed_url": site, "entries": []}


def test_activate_checks_the_feed_and_deactivate_records_why(
    db: Session, made: dict[str, list[int]], monkeypatch: pytest.MonkeyPatch
) -> None:
    p = _publisher(db, made, disabled_reason="probe 1/10")
    feed_url = f"https://{TAG}.substack.com/feed"
    dead = _rss(("https://a.dev/1", NOW - timedelta(days=100)))
    monkeypatch.setattr(sources, "_get", lambda u: dead)
    with pytest.raises(SourceError, match="Newest post"):
        sources.activate_publisher(db, p.slug, feed_url, None, "probe 3/4", NOW)

    live = _rss(("https://a.dev/2", NOW - timedelta(days=2)))
    monkeypatch.setattr(sources, "_get", lambda u: live)
    with pytest.raises(SourceError, match="exactly one"):
        sources.activate_publisher(db, p.slug, feed_url, "x.dev", "r", NOW)
    with pytest.raises(SourceError, match="reason"):
        sources.activate_publisher(db, p.slug, feed_url, None, " ", NOW)

    assert sources.activate_publisher(db, p.slug, feed_url, None, "3/4", NOW) == (
        f"Activated {p.slug} as substack"
    )
    db.refresh(p)
    assert (p.is_active, p.type, p.disabled_reason) == (
        True,
        PublisherType.substack,
        None,
    )
    assert p.links["substack"] == feed_url  # type: ignore[index]
    with pytest.raises(SourceError, match="already active"):
        sources.activate_publisher(db, p.slug, feed_url, None, "3/4", NOW)

    sources.deactivate_publisher(db, p.slug, "culled 0/12 90d", NOW)
    db.refresh(p)
    assert (p.is_active, p.disabled_reason) == (False, "culled 0/12 90d")


def test_search_is_only_for_a_lab_or_company_on_its_own_site(
    db: Session, made: dict[str, list[int]]
) -> None:
    person = _publisher(db, made)
    with pytest.raises(SourceError, match="labs and companies"):
        sources.activate_publisher(db, person.slug, None, "x.dev", "r", NOW)

    lab = _publisher(db, made, kind=PublisherKind.lab)
    site = lab.links["website"].removeprefix("https://")  # type: ignore[index]
    with pytest.raises(SourceError, match="not"):
        sources.activate_publisher(db, lab.slug, None, "other.dev", "r", NOW)
    sources.activate_publisher(db, lab.slug, None, site, "3/3 prior", NOW)
    db.refresh(lab)
    assert (lab.type, lab.links["search"]) == (PublisherType.search, site)  # type: ignore[index]
