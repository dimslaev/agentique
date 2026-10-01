"""The newsletter's reads against the real schema, with the embedding stubbed.

The grouping maths is curation's and pinned there. This pins what the
newsletter adds: that `week` ranks topics by how many publishers carried them,
counting the copies curation rejected, and that `related` reaches the
individual review, the repo and the commentary, and nothing outside the window.
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

    Against ``_axis(i)``, a wobble of 0.05 or -0.5 is the same story (distance
    under 0.30) and 1.2 is the same subject, a different story (~0.36). Rows on
    opposite sides of the axis stay apart, so no row sits between two articles
    and joins them into one topic.
    """
    v = np.zeros(DIM, dtype=np.float32)
    v[200 + i] = 1.0
    v[250] = wobble
    return v.tolist()


def _noise(text: str) -> list[float]:
    seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
    return np.random.default_rng(seed).standard_normal(DIM).tolist()


# Title -> vector, for the ledger rows (embedded on the fly).
VECTORS = {
    f"{TAG} Kernels, again": _axis(1, 0.05),
    f"{TAG} Kernels, once more": _axis(1, 0.08),
    f"{TAG} My weekend with Ollama MLX": _axis(0, 1.3),
    f"{TAG} What Ollama MLX means": _axis(0, 1.25),
    f"{TAG} Ollama MLX is bad, a hot take": _axis(0, -0.5),
    f"{TAG} Ollama MLX, still waiting": _axis(0, -0.5),
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
            ("Wired", PublisherKind.media),
            ("Register", PublisherKind.media),
        )
    }
    db.add_all(publishers.values())
    db.commit()
    now = datetime.now(UTC)

    def article(pub: str, url: str, score: int, vec: list[float], **kw):
        return Article(
            title=f"{TAG} {url}",
            url=url,
            publisher_id=publishers[pub].id or 0,
            score=score,
            embedding=vec,
            summary=f"summary of {url}",
            **kw,
        )

    def reject(url: str, title: str, score: int, pub: str | None = None, **kw):
        return Reject(
            url=url,
            stage=kw.pop("stage", RejectStage.below_threshold),
            title=f"{TAG} {title}",
            publisher_id=publishers[pub].id if pub else None,
            score=score,
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
    kernels = article("Blog", _url("blog.example", "kernels"), 80, _axis(1))
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
    rejects = {
        "wired": reject(
            _url("wired.example", "kernels"),
            "Kernels, again",
            40,
            "Wired",
            reason="Retelling of the kernel post.",
        ),
        "register": reject(
            _url("register.example", "kernels"), "Kernels, once more", 38, "Register"
        ),
        "weekend": reject(
            _url("reader.example", "weekend"),
            "My weekend with Ollama MLX",
            70,
            "Writer",
            reason="Retelling of a release the feed already carries.",
        ),
        "take": reject(
            _url("reader.example", "take"),
            "What Ollama MLX means",
            40,
            reason="Commentary with nothing to check.",
        ),
        "hot_take": reject(
            _url("reader.example", "hot-take"), "Ollama MLX is bad, a hot take", 30
        ),
        "pending": reject(
            _url("reader.example", "pending"),
            "Ollama MLX, still waiting",
            0,
            stage=RejectStage.pending,
        ),
    }
    db.add_all([release, retelling, review, repo, kernels, minor, ancient, marked])
    db.add_all(rejects.values())
    db.commit()
    user = create_random_user(db)
    db.add(ArticleLike(user_id=user.id, article_id=release.id or 0))
    db.commit()

    yield {
        "release": release.url,
        "retelling": retelling.url,
        "review": review.url,
        "repo": repo.url,
        "kernels": kernels.url,
        "minor": minor.url,
        "ancient": ancient.url,
        "marked": marked.url,
        **{name: r.url for name, r in rejects.items()},
    }

    db.exec(delete(ArticleLike).where(col(ArticleLike.user_id) == user.id))
    db.exec(delete(Reject).where(col(Reject.url).contains(TAG)))
    db.exec(delete(Article).where(col(Article.url).contains(TAG)))
    db.exec(delete(Publisher).where(col(Publisher.slug).startswith(TAG)))
    db.delete(user)
    db.commit()


def _ours(db: Session) -> list[digest.WeekTopic]:
    # A high limit: the local db carries other articles from this week.
    return [
        t
        for t in digest.week(db, limit=1000)
        if any(TAG in a["url"] for a in t["articles"])
    ]


def _topic(db: Session, url: str) -> digest.WeekTopic:
    [topic] = [t for t in _ours(db) if t["articles"][0]["url"] == url]
    return topic


def test_week_ranks_topics_by_how_many_publishers_carried_them(
    db: Session, world: dict
):
    """The kernel post scores lowest of the three, and two outlets whose copies
    curation rejected carried it too: it is the week's most talked-about."""
    assert [t["articles"][0]["url"] for t in _ours(db)] == [
        world["kernels"],
        world["release"],
        world["review"],
        world["minor"],
    ]


def test_week_counts_the_rejected_copies_as_coverage(db: Session, world: dict):
    topic = _topic(db, world["kernels"])
    assert topic["coverage"] == 3
    assert topic["publishers"] == [f"{TAG} Blog", f"{TAG} Register", f"{TAG} Wired"]
    assert {c["url"] for c in topic["covered_by"]} == {
        world["wired"],
        world["register"],
    }
    [wired] = [c for c in topic["covered_by"] if c["url"] == world["wired"]]
    assert wired["reason"] == "Retelling of the kernel post."


def test_a_week_topic_carries_its_articles_likes_and_summaries(
    db: Session, world: dict
):
    topic = _topic(db, world["release"])
    assert [a["url"] for a in topic["articles"]] == [
        world["release"],
        world["retelling"],
    ]
    # Rows with no publisher join the topic without counting as coverage.
    assert topic["coverage"] == 2
    assert {world["hot_take"], world["pending"]} <= {
        c["url"] for c in topic["covered_by"]
    }
    assert topic["likes"] == 1
    assert topic["top_score"] == 92
    lead = topic["articles"][0]
    assert lead["publisher_kind"] == "company"
    assert lead["summary"] == f"summary of {world['release']}"


def test_week_leaves_out_what_is_not_this_weeks(db: Session, world: dict):
    urls = {a["url"] for t in _ours(db) for a in t["articles"]}
    for name in ("repo", "ancient", "marked"):
        assert world[name] not in urls


def test_week_returns_at_most_limit_topics(db: Session, world: dict):
    assert world
    assert len(digest.week(db, limit=1)) == 1


def test_related_reaches_the_review_the_repo_and_the_commentary(
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
    # Commentary scores under the approve line and still counts.
    assert rows[world["take"]]["score"] == 40
    distances = [r["distance"] for r in result["rows"]]
    assert distances == sorted(distances)


def test_related_leaves_out_slop_the_queue_and_the_window(db: Session, world: dict):
    urls = {r["url"] for r in digest.related(db, world["release"])["rows"]}
    for name in ("release", "hot_take", "pending", "ancient", "marked", "kernels"):
        assert world[name] not in urls


def test_related_on_an_unknown_url_is_a_message(db: Session, world: dict):
    with pytest.raises(digest.DigestError, match="No published article"):
        digest.related(db, world["pending"])
