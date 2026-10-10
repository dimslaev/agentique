"""The topic map file: its window, its clusters, its labels, and how it lands.

The clustering and layout are pure, so they run on made-up vectors: tight
groups along separate axes, which any sane k-means splits the same way. The
window and the read are pinned against the real schema, dated far in the
future so nothing else in the test database falls inside it.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from sqlmodel import Session, col, delete, select

from app.catalog.models import (
    Article,
    ArticleTag,
    Publisher,
    PublisherKind,
    PublisherType,
    Tag,
)
from pipeline import topic_map
from pipeline.topic_map import (
    MIN_POINTS,
    MONTH_DAYS,
    WEEK_DAYS,
    Point,
    TopicMap,
    build,
    cluster_labels,
    fold_small,
    window_days,
    write_atomic,
)
from tests.random_data import random_lower_string

DIM = 256
NOW = datetime(2100, 1, 15, 6, 10, tzinfo=UTC)


def _group(axis: int, size: int, tags: list[str], seed: int) -> list[Point]:
    rng = np.random.default_rng(seed)
    out = []
    for i in range(size):
        v = rng.normal(0, 0.05, DIM)
        v[axis] += 1.0
        out.append(
            Point(
                id=axis * 1000 + i,
                title=f"Article {axis}-{i}",
                url=f"https://example.com/{axis}/{i}",
                publisher=f"Publisher {axis}",
                score=50 + (i * 7) % 50,
                vector=v.tolist(),
                tags=list(tags),
            )
        )
    return out


def _world() -> list[Point]:
    # Four topics. "agents" is on every article, so it names none of them.
    return (
        _group(0, 14, ["agents", "retrieval"], 1)
        + _group(1, 12, ["agents", "open weights"], 2)
        + _group(2, 10, ["agents", "evals"], 3)
        + _group(3, 9, ["agents", "inference"], 4)
    )


def _build(points: list[Point]) -> TopicMap:
    return build(points, WEEK_DAYS, NOW - timedelta(days=WEEK_DAYS), NOW)


# ─── window ──────────────────────────────────────────────────────────────────


def test_the_window_is_a_week_from_min_points():
    assert window_days(MIN_POINTS) == WEEK_DAYS
    assert window_days(MIN_POINTS + 40) == WEEK_DAYS


def test_the_window_is_a_month_below_min_points():
    assert window_days(MIN_POINTS - 1) == MONTH_DAYS
    assert window_days(0) == MONTH_DAYS


# ─── clusters ────────────────────────────────────────────────────────────────


def test_the_same_input_gives_the_same_file():
    assert json.dumps(_build(_world())) == json.dumps(_build(_world()))


def test_each_topic_is_one_cluster():
    data = _build(_world())
    by_publisher: dict[str, set[int]] = {}
    for p in data["points"]:
        by_publisher.setdefault(p["publisher"], set()).add(p["cluster"])
    assert all(len(c) == 1 for c in by_publisher.values())
    assert len({next(iter(c)) for c in by_publisher.values()}) == 4


def test_small_clusters_fold_into_the_nearest():
    x = np.array([[0.0, 0.0], [0.1, 0.0], [0.0, 0.1], [5.0, 5.0], [5.1, 5.0]])
    # Two points near (5, 5) on their own, and a cluster beside them.
    x = np.vstack([x, [[4.9, 4.9], [5.0, 5.2], [5.2, 5.1]]])
    labels = np.array([0, 0, 0, 1, 1, 2, 2, 2])
    folded = fold_small(x, labels)
    assert set(folded[3:5].tolist()) == {folded[5]}
    assert min(Counter(folded.tolist()).values()) >= topic_map.MIN_CLUSTER


def test_no_cluster_in_the_file_is_under_the_minimum():
    stray = _group(4, 2, ["agents"], 5)
    data = _build(_world() + stray)
    assert all(c["size"] >= topic_map.MIN_CLUSTER for c in data["clusters"])


def test_centres_keep_their_distance():
    data = _build(_world() + _group(4, 6, ["agents", "voice"], 6))
    centres = np.array([[c["x"], c["y"]] for c in data["clusters"]])
    gaps = [
        np.linalg.norm(a - b) for i, a in enumerate(centres) for b in centres[i + 1 :]
    ]
    assert min(gaps) >= topic_map.MIN_GAP - 0.01


# ─── labels ──────────────────────────────────────────────────────────────────


def test_labels_name_the_distinctive_tag_not_the_common_one():
    data = _build(_world())
    labels = {c["label"] for c in data["clusters"]}
    assert labels == {"retrieval", "open weights", "evals", "inference"}


def test_a_rare_tag_does_not_outrank_the_one_most_of_the_cluster_carries():
    # NVIDIA sits only in cluster 0, so its lift (2) beats Evaluation's (1.5),
    # but 6 of 10 articles there are Evaluation and 2 are NVIDIA.
    tags = (
        [["Evaluation"]] * 6
        + [["NVIDIA"]] * 2
        + [["Coding"]] * 2
        + [["Evaluation"]] * 2
        + [["Coding"]] * 8
    )
    labels = np.array([0] * 10 + [1] * 10)
    assert cluster_labels(tags, labels)[0] == "Evaluation"


def test_a_cluster_with_no_distinctive_tag_is_other():
    points = _group(0, 8, ["agents"], 1) + _group(1, 8, ["agents"], 2)
    data = _build(points)
    assert {c["label"] for c in data["clusters"]} == {"other"}


# ─── schema ──────────────────────────────────────────────────────────────────


def test_the_file_matches_schema_v1():
    data = _build(_world())
    assert set(data) == {
        "v",
        "generated_at",
        "window_days",
        "since",
        "count",
        "clusters",
        "points",
    }
    assert data["v"] == 1
    assert data["window_days"] == WEEK_DAYS
    assert datetime.fromisoformat(data["generated_at"]) == NOW
    assert datetime.fromisoformat(data["since"]) == NOW - timedelta(days=WEEK_DAYS)
    assert data["count"] == len(data["points"]) == 45
    assert 4 <= len(data["clusters"]) <= 8

    for c in data["clusters"]:
        assert set(c) == {"id", "label", "x", "y", "size"}
        assert 0.12 <= c["x"] <= 0.88 and 0.12 <= c["y"] <= 0.88
    assert sum(c["size"] for c in data["clusters"]) == data["count"]
    assert [c["id"] for c in data["clusters"]] == list(range(len(data["clusters"])))

    ids = {c["id"] for c in data["clusters"]}
    for p in data["points"]:
        assert set(p) == {
            "id",
            "x",
            "y",
            "cluster",
            "score",
            "title",
            "url",
            "publisher",
        }
        assert 0 <= p["x"] <= 1 and 0 <= p["y"] <= 1
        assert p["cluster"] in ids
    json.dumps(data)


def test_an_empty_window_still_writes_a_file():
    data = _build([])
    assert data["count"] == 0
    assert data["clusters"] == [] and data["points"] == []


# ─── writing ─────────────────────────────────────────────────────────────────


def test_the_write_lands_whole(tmp_path: Path):
    path = tmp_path / "data" / "topic-map.json"
    write_atomic(path, _build(_world()))
    assert json.loads(path.read_text())["count"] == 45
    assert path.stat().st_mode & 0o777 == 0o644
    assert [p.name for p in path.parent.iterdir()] == ["topic-map.json"]


def test_an_interrupted_write_leaves_the_last_good_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "topic-map.json"
    write_atomic(path, _build([]))

    def crash(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(json, "dump", crash)
    with pytest.raises(KeyboardInterrupt):
        write_atomic(path, _build(_world()))
    assert json.loads(path.read_text())["count"] == 0
    assert [p.name for p in tmp_path.iterdir()] == ["topic-map.json"]


def test_the_path_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TOPIC_MAP_PATH", "/srv/x/topic-map.json")
    assert topic_map.output_path() == Path("/srv/x/topic-map.json")
    monkeypatch.delenv("TOPIC_MAP_PATH")
    assert topic_map.output_path().parts[-3:] == ("public", "data", "topic-map.json")


# ─── against the schema ──────────────────────────────────────────────────────

TAG = random_lower_string()[:8]


@pytest.fixture
def publisher(db: Session) -> Generator[Publisher]:
    p = Publisher(
        name=f"{TAG} Blog",
        slug=f"{TAG}-blog",
        kind=PublisherKind.individual,
        type=PublisherType.rss,
    )
    db.add(p)
    db.commit()
    yield p
    articles = select(Article.id).where(col(Article.publisher_id) == p.id)
    db.exec(delete(ArticleTag).where(col(ArticleTag.article_id).in_(articles)))
    db.exec(delete(Article).where(col(Article.publisher_id) == p.id))
    db.exec(delete(Tag).where(col(Tag.slug).startswith(TAG)))
    db.delete(p)
    db.commit()


def _add(db: Session, publisher: Publisher, n: int, days_ago: float) -> None:
    rng = np.random.default_rng(n)
    for i in range(n):
        db.add(
            Article(
                title=f"{TAG} {days_ago} {i}",
                url=f"https://example.com/{TAG}/{days_ago}/{i}",
                publisher_id=publisher.id or 0,
                score=40 + i % 60,
                embedding=rng.standard_normal(DIM).tolist(),
                created_at=NOW - timedelta(days=days_ago),
            )
        )
    db.commit()


def test_a_sparse_week_reads_the_month(db: Session, publisher: Publisher):
    _add(db, publisher, MIN_POINTS - 1, days_ago=2)
    _add(db, publisher, 10, days_ago=20)
    days, since, points = topic_map.read_points(db, NOW)
    assert days == MONTH_DAYS
    assert since == NOW - timedelta(days=MONTH_DAYS)
    assert len(points) == MIN_POINTS - 1 + 10


def test_a_full_week_reads_the_week_by_score(db: Session, publisher: Publisher):
    _add(db, publisher, MIN_POINTS, days_ago=2)
    _add(db, publisher, 10, days_ago=20)
    tag = Tag(slug=f"{TAG}-evals", name="Evals")
    db.add(tag)
    db.commit()
    top = db.exec(
        select(Article)
        .where(col(Article.publisher_id) == publisher.id)
        .order_by(col(Article.score).desc(), col(Article.id))
    ).first()
    assert top is not None
    db.add(ArticleTag(article_id=top.id or 0, tag_id=tag.id or 0))
    db.commit()

    days, _, points = topic_map.read_points(db, NOW)
    assert days == WEEK_DAYS
    assert len(points) == MIN_POINTS
    assert [p.score for p in points] == sorted((p.score for p in points), reverse=True)
    assert points[0].tags == ["Evals"]
    assert points[0].publisher == publisher.name
    assert len(points[0].vector) == DIM
