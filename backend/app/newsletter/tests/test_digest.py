"""The newsletter's reads against the real schema, with the embedding stubbed.

The grouping maths is curation's and pinned there. This pins what the
newsletter adds: that `week` keeps every article in exactly one story and
ranks them, and that `related` reaches the individual review, the repo and the
reject that curation turned down as a retelling, and nothing outside the window.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlmodel import Session, col, delete

from app.audience.models import ArticleLike
from app.audience.tests.factories import create_random_user
from app.catalog.models import (
    Article,
    ArticleKind,
    Publisher,
    PublisherKind,
    PublisherType,
)
from app.newsletter import digest
from pipeline.models import Reject, RejectStage
from tests.random_data import random_lower_string

DIM = 256
TAG = random_lower_string()[:8]


def _axis(i: int, wobble: float = 0.0) -> list[float]:
    """A vector along one of the high axes, far from anything real.

    Against ``_axis(i)``, a wobble of 0.05 is the same story (distance ~0.001),
    1.0 is the same subject (~0.29) and 1.2 is related but a different story
    (~0.36).
    """
    v = np.zeros(DIM, dtype=np.float32)
    v[200 + i] = 1.0
    v[250] = wobble
    return v.tolist()


def _noise(text: str) -> list[float]:
    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    return np.random.default_rng(seed).standard_normal(DIM).tolist()


# Title -> vector, for the rows embedded on the fly (no stored embedding).
VECTORS = {
    f"{TAG} My weekend with Ollama MLX": _axis(0, 1.1),
    f"{TAG} Ollama MLX is bad, a hot take": _axis(0, 0.9),
    f"{TAG} Ollama MLX, still waiting": _axis(0, 0.9),
}


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [VECTORS.get(t.split("\n\n")[0], _noise(t)) for t in texts]


def _url(host: str, path: str) -> str:
    return f"https://{host}/{TAG}/{path}"


@pytest.fixture
def world(db: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[dict]:
    monkeypatch.setattr(digest, "embed_batch", _fake_embed)

    publishers = {
        name: Publisher(
            name=f"{TAG} {name}",
            slug=f"{TAG}-{name.lower()}",
            kind=kind,
            type=PublisherType.rss,
        )
        for name, kind in (
            ("Ollama", PublisherKind.company),
            ("Verge", PublisherKind.media),
            ("Writer", PublisherKind.individual),
            ("Maker", PublisherKind.individual),
            ("Blog", PublisherKind.media),
        )
    }
    db.add_all(publishers.values())
    db.commit()
    now = datetime.now(UTC)

    def article(pub: str, url: str, score: int, vec: list[float] | None, **kw):
        return Article(
            title=f"{TAG} {url}",
            url=url,
            publisher_id=publishers[pub].id or 0,
            score=score,
            embedding=vec,
            summary=f"summary of {url}",
            **kw,
        )

    release = article("Ollama", _url("ollama.example", "mlx"), 92, _axis(0))
    retelling = article("Verge", _url("verge.example", "mlx"), 75, _axis(0, 0.05))
    review = article("Writer", _url("writer.example", "mlx"), 84, _axis(0, 1.2))
    repo = article(
        "Maker",
        f"https://github.com/{TAG}/ollama-ci",
        72,
        _axis(0, 1.0),
        kind=ArticleKind.repo,
        created_at=now - timedelta(days=20),
    )
    lone = article("Blog", _url("blog.example", "kernels"), 80, _axis(1))
    minor = article("Blog", _url("blog.example", "minor"), 60, _axis(2))
    ancient = article(
        "Blog",
        _url("blog.example", "ancient"),
        90,
        _axis(0),
        created_at=now - timedelta(days=40),
    )
    marked = article(
        "Blog",
        _url("blog.example", "marked"),
        90,
        _axis(0),
        marked_for_deletion_at=now,
    )
    rejects = [
        Reject(
            url=_url("reader.example", "weekend"),
            stage=RejectStage.below_threshold,
            title=f"{TAG} My weekend with Ollama MLX",
            publisher_id=publishers["Writer"].id,
            score=70,
            reason="Retelling of a release the feed already carries.",
        ),
        Reject(
            url=_url("reader.example", "hot-take"),
            stage=RejectStage.below_threshold,
            title=f"{TAG} Ollama MLX is bad, a hot take",
            score=30,
            reason="Opinion with nothing to check.",
        ),
        Reject(
            url=_url("reader.example", "pending"),
            stage=RejectStage.pending,
            title=f"{TAG} Ollama MLX, still waiting",
        ),
    ]
    db.add_all([release, retelling, review, repo, lone, minor, ancient, marked])
    db.add_all(rejects)
    db.commit()
    user = create_random_user(db)
    db.add(ArticleLike(user_id=user.id, article_id=release.id or 0))
    db.commit()

    yield {
        "release": release.url,
        "retelling": retelling.url,
        "review": review.url,
        "repo": repo.url,
        "lone": lone.url,
        "minor": minor.url,
        "ancient": ancient.url,
        "marked": marked.url,
        "weekend": rejects[0].url,
        "hot_take": rejects[1].url,
        "pending": rejects[2].url,
    }

    db.exec(delete(ArticleLike).where(col(ArticleLike.user_id) == user.id))
    db.exec(delete(Reject).where(col(Reject.url).contains(TAG)))
    db.exec(delete(Article).where(col(Article.url).contains(TAG)))
    db.exec(delete(Publisher).where(col(Publisher.slug).startswith(TAG)))
    db.delete(user)
    db.commit()


def _ours(stories: list[digest.WeekStory]) -> list[list[str]]:
    return [
        [a["url"] for a in s["articles"]]
        for s in stories
        if any(TAG in a["url"] for a in s["articles"])
    ]


def test_week_groups_one_story_and_keeps_the_rest_on_their_own(
    db: Session, world: dict
):
    assert _ours(digest.week(db)) == [
        [world["release"], world["retelling"]],
        [world["review"]],
        [world["lone"]],
    ]


def test_week_leaves_out_what_the_newsletter_would_not_lead_with(
    db: Session, world: dict
):
    urls = {u for story in _ours(digest.week(db)) for u in story}
    # Under the score floor, older than the week, or marked for deletion.
    for name in ("minor", "repo", "ancient", "marked"):
        assert world[name] not in urls
    assert world["minor"] in {
        u for story in _ours(digest.week(db, min_score=50)) for u in story
    }


def test_a_week_story_carries_coverage_likes_and_the_publisher_kind(
    db: Session, world: dict
):
    [story] = [
        s for s in digest.week(db) if s["articles"][0]["url"] == world["release"]
    ]
    assert story["top_score"] == 92
    assert story["coverage"] == 2
    lead = story["articles"][0]
    assert lead["likes"] == 1
    assert lead["publisher_kind"] == "company"
    assert lead["summary"] == f"summary of {world['release']}"


def test_related_reaches_the_review_the_repo_and_a_retelling_reject(
    db: Session, world: dict
):
    result = digest.related(db, world["release"])
    rows = {r["url"]: r for r in result["rows"]}

    assert rows[world["review"]]["publisher_kind"] == "individual"
    assert rows[world["review"]]["stage"] == digest.PUBLISHED
    # Twenty days old: outside the week, inside the related window.
    assert rows[world["repo"]]["kind"] == "repo"
    weekend = rows[world["weekend"]]
    assert weekend["stage"] == digest.REJECTED
    assert weekend["reason"].startswith("Retelling")
    assert weekend["publisher_kind"] == "individual"
    distances = [r["distance"] for r in result["rows"]]
    assert distances == sorted(distances)


def test_related_leaves_out_weak_rejects_the_queue_and_the_window(
    db: Session, world: dict
):
    urls = {r["url"] for r in digest.related(db, world["release"])["rows"]}
    for name in ("release", "hot_take", "pending", "ancient", "marked", "lone"):
        assert world[name] not in urls


def test_related_on_an_unknown_url_is_a_message(db: Session, world: dict):
    with pytest.raises(digest.DigestError, match="No published article"):
        digest.related(db, world["pending"])
