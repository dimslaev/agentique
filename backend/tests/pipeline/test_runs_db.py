"""The run's bookkeeping and the daily mail's queries, against the real schema."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlmodel import Session, col, delete, select

from app.catalog.models import Article, Publisher, PublisherKind, PublisherType
from pipeline.models import PipelineRun
from pipeline.report import read_night
from pipeline.runs import RunStats, record_new, record_polled, record_run
from tests.random_data import random_lower_string

TAG = random_lower_string()[:8]
EARLIER = datetime(2026, 9, 20, 4, 0, tzinfo=UTC)
NOW = datetime(2026, 9, 23, 4, 0, tzinfo=UTC)


@pytest.fixture
def feeds(db: Session) -> Generator[dict[str, Publisher]]:
    publishers = {
        name: Publisher(
            name=f"{TAG} {name}",
            slug=f"{TAG}-{name.lower()}",
            kind=PublisherKind.media,
            type=PublisherType.rss,
            last_fetched_at=EARLIER,
            last_error="old error" if name == "Healed" else None,
        )
        for name in ("Healed", "Broken", "Quiet")
    }
    db.add_all(publishers.values())
    db.commit()
    yield publishers
    db.exec(delete(Article).where(col(Article.url).contains(TAG)))
    db.exec(delete(Publisher).where(col(Publisher.slug).startswith(TAG)))
    db.commit()


def _fresh(db: Session, p: Publisher) -> Publisher:
    db.refresh(p)
    return p


def test_a_good_fetch_stamps_and_clears_a_failed_one_keeps_the_last_good(
    db: Session, feeds: dict[str, Publisher]
):
    names = [p.name for p in feeds.values()]
    record_polled(db, names, {f"{TAG} Broken": "RuntimeError: 403"}, now=NOW)

    healed = _fresh(db, feeds["Healed"])
    broken = _fresh(db, feeds["Broken"])
    quiet = _fresh(db, feeds["Quiet"])
    assert (healed.last_fetched_at, healed.last_error) == (NOW, None)
    assert (broken.last_fetched_at, broken.last_error) == (EARLIER, "RuntimeError: 403")
    # Answered with nothing new: fetched, not an error.
    assert (quiet.last_fetched_at, quiet.last_error) == (NOW, None)


def test_a_queued_candidate_stamps_its_publisher_new(
    db: Session, feeds: dict[str, Publisher]
):
    record_new(db, [feeds["Healed"].id or 0], now=NOW)
    assert _fresh(db, feeds["Healed"]).last_new_at == NOW
    assert _fresh(db, feeds["Quiet"]).last_new_at is None


def test_the_night_reads_the_last_run_and_the_failing_feeds(
    db: Session, feeds: dict[str, Publisher]
):
    names = [p.name for p in feeds.values()]
    record_polled(db, names, {feeds["Broken"].name: "boom"})
    db.add(
        Article(
            title=f"{TAG} a landed article",
            url=f"https://landed.example/{TAG}",
            publisher_id=feeds["Quiet"].id or 0,
            score=81,
        )
    )
    db.commit()
    stats = RunStats()
    stats.source("Feeds").fetched = 12
    stats.source("Newsletter")
    stats.finish(ok=True)
    run = record_run(db, stats)

    night = read_night(db)

    assert night.liveness is None
    assert night.silent_sources == ["Newsletter"]
    assert (f"{TAG} Broken", "boom") in night.failing_publishers
    assert f"{TAG} Healed" not in [name for name, _ in night.failing_publishers]
    assert any(a.url == f"https://landed.example/{TAG}" for a in night.landed)

    db.exec(delete(PipelineRun).where(col(PipelineRun.id) == run.id))
    db.commit()
    assert (
        db.exec(select(PipelineRun).where(col(PipelineRun.id) == run.id)).first()
        is None
    )
