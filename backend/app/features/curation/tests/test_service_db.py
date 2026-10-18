"""The curation queries against the real schema, with the embedding stubbed.

The pure parts are pinned in test_service.py. This pins what those cannot:
that `similar` and `stories` read the right rows (the feed's stored vectors,
every ledger stage, the window), that `list_candidates` counts a publisher's
record from the right ones, and that approving and rejecting write exactly the
rows they say they do.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlmodel import Session, col, delete, func, select

from app.core.db.article import Article
from app.core.db.ledger import Reject, RejectStage
from app.core.db.publisher import Publisher, PublisherKind, PublisherType
from app.core.db.tag import ArticleTag, Tag
from app.features.curation import coverage, publish
from app.features.curation import service as curation
from app.features.curation.model import CandidateError
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
    return [float(x) for x in np.random.default_rng(seed).standard_normal(DIM)]


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
def world(db: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[dict[str, str]]:
    monkeypatch.setattr(curation, "embed_batch", _fake_embed)
    monkeypatch.setattr(coverage, "embed_batch", _fake_embed)

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


def test_similar_lists_the_feed_and_every_ledger_stage(
    db: Session, world: dict[str, str]
) -> None:
    result = curation.similar(db, world["verge"])

    urls = [r["url"] for r in result["rows"]]
    assert urls[:2] == [world["feed"], f"https://wired.example/{TAG}/astra"]
    stages = {r["url"]: r["stage"] for r in result["rows"]}
    assert stages[world["feed"]] == coverage.PUBLISHED
    assert stages[f"https://wired.example/{TAG}/astra"] == "below_threshold"
    # Outside the window: the 30-day-old article is not a neighbour.
    assert f"https://old.example/{TAG}/rumour" not in urls
    # Never its own neighbour.
    assert world["verge"] not in urls


def test_similar_counts_coverage_by_publisher(
    db: Session, world: dict[str, str]
) -> None:
    result = curation.similar(db, world["verge"])
    assert result["publishers"] == [f"{TAG} OpenAI", f"{TAG} Verge", f"{TAG} Wired"]
    assert result["coverage"] == 3


def test_a_story_nobody_else_carries_has_coverage_one(
    db: Session, world: dict[str, str]
) -> None:
    result = curation.similar(db, world["lone"])
    assert result["coverage"] == 1
    assert result["publishers"] == [f"{TAG} Blog"]


def test_similar_on_an_unknown_url_is_a_message(
    db: Session, world: dict[str, str]
) -> None:
    with pytest.raises(CandidateError, match="No candidate or article"):
        curation.similar(db, f"https://nowhere.example/{TAG}")
    assert world


def test_stories_groups_the_queue_with_the_feed(
    db: Session, world: dict[str, str]
) -> None:
    groups = [
        g for g in curation.stories(db) if any(TAG in m["url"] for m in g["members"])
    ]

    [story] = groups
    assert {m["url"] for m in story["members"]} == {world["verge"], world["feed"]}
    assert story["coverage"] == 2


def _all_candidates(
    db: Session, limit: int = curation.LIST_LIMIT
) -> list[dict[str, str]]:
    """Every pending row, read page by page as the agent does."""
    page = curation.list_candidates(db, limit=limit)
    rows = page["rows"]
    while page["next_offset"] is not None:
        page = curation.list_candidates(db, offset=page["next_offset"], limit=limit)
        rows += page["rows"]
    return rows


def test_list_candidates_shows_each_publishers_approval_rate(
    db: Session, world: dict[str, str]
) -> None:
    rows = {r["url"]: r for r in _all_candidates(db)}
    # Verge: nothing published, nothing turned down yet.
    assert rows[world["verge"]]["approved"] == "new"
    assert "trust" not in rows[world["verge"]]
    # Blog's one article is 30 days old: outside `similar`'s week, inside the
    # 90 days a record reaches.
    assert rows[world["lone"]]["approved"] == "1/1"


def test_list_candidates_pages_through_the_whole_queue(
    db: Session, world: dict[str, str]
) -> None:
    first = curation.list_candidates(db, limit=1)
    assert first["offset"] == 0
    assert len(first["rows"]) == 1

    urls = [r["url"] for r in _all_candidates(db, limit=1)]

    # Every pending row once, and only pending rows.
    assert len(urls) == len(set(urls)) == first["total"]
    assert {world["verge"], world["lone"]} <= set(urls)
    assert f"https://wired.example/{TAG}/astra" not in urls


def test_list_candidates_past_the_end_is_an_empty_last_page(
    db: Session, world: dict[str, str]
) -> None:
    page = curation.list_candidates(db, offset=10**6)
    assert page["rows"] == []
    assert page["next_offset"] is None
    assert page["offset"] == page["total"]
    assert world


def test_approval_counts_reads_articles_and_agent_rejects(
    db: Session, world: dict[str, str]
) -> None:
    ids = {
        p.name: p.id
        for p in db.exec(select(Publisher).where(col(Publisher.slug).startswith(TAG)))
        if p.id is not None
    }
    since = datetime.now(UTC) - timedelta(days=90)
    counts = curation.approval_counts(db, list(ids.values()), since)

    assert counts[ids[f"{TAG} OpenAI"]] == (1, 0)
    assert counts[ids[f"{TAG} Wired"]] == (0, 1)
    # A pending row is not a decision.
    assert ids[f"{TAG} Verge"] not in counts
    assert world


# ─── approve and reject ──────────────────────────────────────────────────────


@pytest.fixture
def queued(db: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[Reject]:
    """One pending candidate from a publisher the run has just created."""
    monkeypatch.setattr(publish, "embed_batch", _fake_embed)
    publisher = Publisher(
        name=f"{TAG}.dev",
        slug=f"{TAG}-dev",
        kind=PublisherKind.unknown,
        is_active=False,
    )
    db.add(publisher)
    db.commit()
    row = Reject(
        url=f"https://{TAG}.dev/post",
        stage=RejectStage.pending,
        title=f"{TAG} — An agent harness, measured",
        source="Hacker News",
        publisher_id=publisher.id,
        content="x" * 5000,
    )
    db.add(row)
    db.commit()
    yield row

    ids = select(Article.id).where(col(Article.url).contains(TAG))
    db.exec(delete(ArticleTag).where(col(ArticleTag.article_id).in_(ids)))
    db.exec(delete(Reject).where(col(Reject.url).contains(TAG)))
    db.exec(delete(Article).where(col(Article.url).contains(TAG)))
    db.exec(delete(Publisher).where(col(Publisher.slug).startswith(TAG)))
    db.commit()


def _a_tag(db: Session) -> str:
    tag = db.exec(select(Tag).order_by(col(Tag.slug))).first()
    assert tag is not None, "the tag vocabulary is seeded by prestart"
    return tag.slug


def test_approving_writes_one_article_and_settles_the_candidate(
    db: Session, queued: Reject
) -> None:
    slug = _a_tag(db)
    article_id = curation.approve(
        db,
        queued.url,
        81,
        "Numbers from a real run.",
        "What the harness got right.",
        "Post",
        [slug, "not-a-tag"],
        publisher_kind="individual",
        publisher_name=f" {TAG} Writer ",
    )

    db.expire_all()
    article = db.get(Article, article_id)
    assert article is not None
    assert (article.url, article.score, article.kind) == (queued.url, 81, "post")
    # Sanitized on the way in, as every stored title is.
    assert article.title == f"{TAG} - An agent harness, measured"
    assert article.found_via == "Hacker News"
    assert article.embedding is not None
    assert db.get(Reject, queued.url) is None
    tags = db.exec(
        select(Tag.slug)
        .join(ArticleTag, col(ArticleTag.tag_id) == col(Tag.id))
        .where(col(ArticleTag.article_id) == article_id)
    ).all()
    assert list(tags) == [slug]
    publisher = db.get(Publisher, article.publisher_id)
    assert publisher is not None
    assert (publisher.kind, publisher.name) == (
        PublisherKind.individual,
        f"{TAG} Writer",
    )


def test_a_candidate_is_published_once(db: Session, queued: Reject) -> None:
    def approve() -> int:
        return curation.approve(db, queued.url, 81, "r", "s", "post", [], "media")

    approve()
    with pytest.raises(CandidateError, match="No candidate"):
        approve()
    count = db.exec(
        select(func.count()).select_from(Article).where(Article.url == queued.url)
    ).one()
    assert count == 1


def test_a_refused_approval_writes_nothing(db: Session, queued: Reject) -> None:
    """approve checks the labels before it touches the candidate."""
    with pytest.raises(CandidateError, match="publisher_kind"):
        curation.approve(db, queued.url, 81, "r", "s", "post", [])

    db.expire_all()
    row = db.get(Reject, queued.url)
    assert row is not None and row.stage == RejectStage.pending
    assert db.exec(select(Article).where(Article.url == queued.url)).first() is None


def test_a_failed_embedding_still_publishes(
    db: Session, queued: Reject, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_texts: list[str]) -> list[list[float]]:
        raise RuntimeError("model download blocked")

    monkeypatch.setattr(publish, "embed_batch", broken)

    article_id = curation.approve(db, queued.url, 81, "r", "s", "post", [], "media")

    db.expire_all()
    article = db.get(Article, article_id)
    assert article is not None and article.embedding is None


def test_a_rejected_candidate_cannot_then_be_approved(
    db: Session, queued: Reject
) -> None:
    curation.reject(db, queued.url, 22, "A vendor tutorial.")

    with pytest.raises(CandidateError, match="already below_threshold"):
        curation.approve(db, queued.url, 81, "r", "s", "post", [], "media")
    db.expire_all()
    row = db.get(Reject, queued.url)
    assert row is not None
    assert (row.stage, row.score, row.reason) == (
        RejectStage.below_threshold,
        22,
        "A vendor tutorial.",
    )
    assert row.content is not None and len(row.content) < 5000


def test_a_url_twice_in_one_batch_is_rejected_once(db: Session, queued: Reject) -> None:
    lines = curation.reject_many(
        db,
        [
            {"url": queued.url, "score": 20, "reason": "first"},
            {"url": queued.url, "score": 90, "reason": "second"},
        ],
    )

    assert lines[0] == f"Rejected [20/100] {queued.url}"
    assert lines[1].startswith(f"Skipped {queued.url}: ")
    db.expire_all()
    row = db.get(Reject, queued.url)
    assert row is not None and (row.score, row.reason) == (20, "first")
