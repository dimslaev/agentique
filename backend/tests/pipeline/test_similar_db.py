"""`similar` and `stories` against the real schema, with the embedding stubbed.

The distance maths is pinned on synthetic vectors in test_curation.py. This
pins the part those cannot: that the queries read the right rows (the feed's
stored vectors, every ledger stage, the window), and that the rows come back
with their publisher and stage.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlmodel import Session, col, delete

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
