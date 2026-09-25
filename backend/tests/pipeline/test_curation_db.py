"""The curation queries against the real schema, with the embedding stubbed.

The pure parts are pinned in test_curation.py. This pins what those cannot:
that `similar` and `stories` read the right rows (the feed's stored vectors,
every ledger stage, the window) and that `list_candidates` counts a publisher's
record from the right ones.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlmodel import Session, col, delete, select

from app.catalog.models import Article, Publisher, PublisherKind, PublisherType
from pipeline import curation
from pipeline.models import Reject, RejectStage
from tests.random_data import random_lower_string

DIM = 256
TAG = random_lower_string()[:8]


def _axis(i: int, wobble: float = 0.0) -> list[float]:
    """A unit-ish vector along one of the high axes, far from anything real."""
    v = np.zeros(DIM, dtype=np.float32)
    v[200 + i] = 1.0
    v[250] = wobble
    return v.tolist()


def _noise(text: str) -> list[float]:
    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    return np.random.default_rng(seed).standard_normal(DIM).tolist()


# Title -> vector. Everything else embeds to deterministic noise.
VECTORS = {
    f"{TAG} GPT-6 Astra ships": _axis(0),
    f"{TAG} OpenAI releases GPT-6 Astra": _axis(0, 0.05),
    f"{TAG} Astra is here, a retelling": _axis(0, 0.10),
    f"{TAG} An old Astra rumour": _axis(0, 0.02),
    f"{TAG} A lone post about kernels": _axis(1),
}


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [VECTORS.get(t.split("\n\n")[0], _noise(t)) for t in texts]


@pytest.fixture
def world(db: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[dict]:
    monkeypatch.setattr(curation, "embed_batch", _fake_embed)

    publishers = [
        Publisher(
            name=f"{TAG} {name}",
            slug=f"{TAG}-{name.lower()}",
            kind=PublisherKind.media,
            type=PublisherType.rss,
        )
        for name in ("OpenAI", "Verge", "Wired", "Blog")
    ]
    db.add_all(publishers)
    db.commit()
    openai, verge, wired, blog = publishers
    now = datetime.now(UTC)

    feed = Article(
        title=f"{TAG} OpenAI releases GPT-6 Astra",
        url=f"https://openai.example/{TAG}/astra",
        publisher_id=openai.id or 0,
        score=90,
        embedding=_axis(0, 0.05),
    )
    old = Article(
        title=f"{TAG} An old Astra rumour",
        url=f"https://old.example/{TAG}/rumour",
        publisher_id=blog.id or 0,
        score=60,
        embedding=_axis(0, 0.02),
        created_at=now - timedelta(days=30),
    )
    pending = [
        Reject(
            url=f"https://verge.example/{TAG}/astra",
            stage=RejectStage.pending,
            title=f"{TAG} GPT-6 Astra ships",
            publisher_id=verge.id,
            content="body",
        ),
        Reject(
            url=f"https://blog.example/{TAG}/kernels",
            stage=RejectStage.pending,
            title=f"{TAG} A lone post about kernels",
            publisher_id=blog.id,
            content="body",
        ),
    ]
    rejected = Reject(
        url=f"https://wired.example/{TAG}/astra",
        stage=RejectStage.below_threshold,
        title=f"{TAG} Astra is here, a retelling",
        publisher_id=wired.id,
        content="body",
        score=30,
    )
    db.add_all([feed, old, *pending, rejected])
    db.commit()

    yield {"verge": pending[0].url, "lone": pending[1].url, "feed": feed.url}

    db.exec(delete(Reject).where(col(Reject.url).contains(TAG)))
    db.exec(delete(Article).where(col(Article.url).contains(TAG)))
    db.exec(delete(Publisher).where(col(Publisher.slug).startswith(TAG)))
    db.commit()


def test_similar_lists_the_feed_and_every_ledger_stage(db: Session, world: dict):
    result = curation.similar(db, world["verge"])

    urls = [r["url"] for r in result["rows"]]
    assert urls[:2] == [world["feed"], f"https://wired.example/{TAG}/astra"]
    stages = {r["url"]: r["stage"] for r in result["rows"]}
    assert stages[world["feed"]] == curation.PUBLISHED
    assert stages[f"https://wired.example/{TAG}/astra"] == "below_threshold"
    # Outside the window: the 30-day-old article is not a neighbour.
    assert f"https://old.example/{TAG}/rumour" not in urls
    # Never its own neighbour.
    assert world["verge"] not in urls


def test_similar_counts_coverage_by_publisher(db: Session, world: dict):
    result = curation.similar(db, world["verge"])
    assert result["publishers"] == [f"{TAG} OpenAI", f"{TAG} Verge", f"{TAG} Wired"]
    assert result["coverage"] == 3


def test_a_story_nobody_else_carries_has_coverage_one(db: Session, world: dict):
    result = curation.similar(db, world["lone"])
    assert result["coverage"] == 1
    assert result["publishers"] == [f"{TAG} Blog"]


def test_similar_on_an_unknown_url_is_a_message(db: Session, world: dict):
    with pytest.raises(curation.CandidateError, match="No candidate or article"):
        curation.similar(db, f"https://nowhere.example/{TAG}")
    assert world


def test_stories_groups_the_queue_with_the_feed(db: Session, world: dict):
    groups = [
        g for g in curation.stories(db) if any(TAG in m["url"] for m in g["members"])
    ]

    [story] = groups
    assert {m["url"] for m in story["members"]} == {world["verge"], world["feed"]}
    assert story["coverage"] == 2


def _all_candidates(db: Session, limit: int = curation.LIST_LIMIT) -> list[dict]:
    """Every pending row, read page by page as the agent does."""
    page = curation.list_candidates(db, limit=limit)
    rows = page["rows"]
    while page["next_offset"] is not None:
        page = curation.list_candidates(db, offset=page["next_offset"], limit=limit)
        rows += page["rows"]
    return rows


def test_list_candidates_shows_each_publishers_approval_rate(db: Session, world: dict):
    rows = {r["url"]: r for r in _all_candidates(db)}
    # Verge: nothing published, nothing turned down yet.
    assert rows[world["verge"]]["approved"] == "new"
    assert "trust" not in rows[world["verge"]]
    # Blog's one article is 30 days old: outside `similar`'s week, inside the
    # 90 days a record reaches.
    assert rows[world["lone"]]["approved"] == "1/1"


def test_list_candidates_pages_through_the_whole_queue(db: Session, world: dict):
    first = curation.list_candidates(db, limit=1)
    assert first["offset"] == 0
    assert len(first["rows"]) == 1

    urls = [r["url"] for r in _all_candidates(db, limit=1)]

    # Every pending row once, and only pending rows.
    assert len(urls) == len(set(urls)) == first["total"]
    assert {world["verge"], world["lone"]} <= set(urls)
    assert f"https://wired.example/{TAG}/astra" not in urls


def test_list_candidates_past_the_end_is_an_empty_last_page(db: Session, world: dict):
    page = curation.list_candidates(db, offset=10**6)
    assert page["rows"] == []
    assert page["next_offset"] is None
    assert page["offset"] == page["total"]
    assert world


def test_approval_counts_reads_articles_and_agent_rejects(db: Session, world: dict):
    ids = {
        p.name: p.id
        for p in db.exec(select(Publisher).where(col(Publisher.slug).startswith(TAG)))
    }
    since = datetime.now(UTC) - timedelta(days=90)
    counts = curation.approval_counts(db, [i for i in ids.values() if i], since)

    assert counts[ids[f"{TAG} OpenAI"]] == (1, 0)
    assert counts[ids[f"{TAG} Wired"]] == (0, 1)
    # A pending row is not a decision.
    assert ids[f"{TAG} Verge"] not in counts
    assert world
