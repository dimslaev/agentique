"""The topic map's data file. Run with: python -m pipeline.topic_map

Every recent article as a point, grouped by meaning into labelled clusters, for
the left rail. Built nightly from the stored embeddings and written as a static
JSON file the frontend reads directly: no API call, no LLM.

The window is a week when the week has enough articles to make a map, and a
month otherwise. Deciding that costs one COUNT. The same articles always give
the same picture: input order is fixed, and k-means runs from a fixed seed.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

import numpy as np
from sqlmodel import Session, col, func, select

from app.catalog.models import Article, ArticleTag, Publisher, Tag
from app.newsletter.digest import _vectors
from app.platform.logging import log
from pipeline.db import get_engine

SCHEMA_VERSION = 1
# Under this many articles in the last week, a week is too sparse to cluster,
# so the map falls back to a month.
MIN_POINTS = 60
# The highest-scored this many. More dots than this do not fit the panel.
MAX_POINTS = 300
WEEK_DAYS = 7
MONTH_DAYS = 30
MIN_K = 4
MAX_K = 8
# A cluster smaller than this is noise, not a topic.
MIN_CLUSTER = 3
SEED = 0
KMEANS_ITERATIONS = 100
# Cluster centres sit in this band, so a cluster's dots around its centre stay
# inside 0..1.
CENTRE_LOW, CENTRE_HIGH = 0.12, 0.88
# Centres closer than this get pushed apart, so clusters and their labels do
# not sit on each other. The PCA alone often stacks two of them.
MIN_GAP = 0.3
SPREAD_ITERATIONS = 100
# The radius of the widest cluster; a tighter one draws smaller.
CLUSTER_RADIUS = 0.1
# A tag must label at least this many articles in a cluster to name it.
MIN_TAG_COUNT = 2
# A second tag joins the label only when the label stays this short.
LABEL_CHARS = 18
FALLBACK_LABEL = "other"

DEFAULT_PATH = (
    Path(__file__).resolve().parents[2] / "frontend/public/data/topic-map.json"
)


class MapCluster(TypedDict):
    id: int
    label: str
    # The centre, 0..1.
    x: float
    y: float
    size: int


class MapPoint(TypedDict):
    id: int
    x: float
    y: float
    cluster: int
    score: int
    title: str
    url: str
    publisher: str


class TopicMap(TypedDict):
    """The file, schema v1. The frontend checks ``v`` before reading the rest."""

    v: int
    generated_at: str
    window_days: int
    since: str
    count: int
    clusters: list[MapCluster]
    points: list[MapPoint]


@dataclass(frozen=True)
class Point:
    id: int
    title: str
    url: str
    publisher: str
    score: int
    vector: list[float]
    tags: list[str]


def window_days(week_count: int) -> int:
    return WEEK_DAYS if week_count >= MIN_POINTS else MONTH_DAYS


def cluster_count(n: int) -> int:
    k = min(max(round(math.sqrt(n / 2)), MIN_K), MAX_K)
    return min(k, n)


def read_points(
    session: Session, now: datetime | None = None
) -> tuple[int, datetime, list[Point]]:
    """``(window_days, since, points)``: the window's highest-scored articles."""
    now = now or datetime.now(UTC)
    live = col(Article.marked_for_deletion_at).is_(None)
    week_count = session.exec(
        select(func.count())
        .select_from(Article)
        .where(col(Article.created_at) >= now - timedelta(days=WEEK_DAYS), live)
    ).one()
    days = window_days(week_count)
    since = now - timedelta(days=days)

    rows = session.exec(
        select(Article, Publisher)
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .where(col(Article.created_at) >= since, live)
        .order_by(col(Article.score).desc(), col(Article.id))
        .limit(MAX_POINTS)
    ).all()
    if not rows:
        return days, since, []

    articles = [a for a, _ in rows]
    tags: dict[int, list[str]] = {}
    for article_id, name in session.exec(
        select(ArticleTag.article_id, Tag.name)
        .join(Tag, col(Tag.id) == col(ArticleTag.tag_id))
        .where(col(ArticleTag.article_id).in_([a.id for a in articles]))
        .order_by(col(Tag.name))
    ).all():
        tags.setdefault(article_id, []).append(name)

    points = [
        Point(
            id=a.id or 0,
            title=a.title,
            url=a.url,
            publisher=p.name,
            score=a.score,
            vector=v,
            tags=tags.get(a.id or 0, []),
        )
        for (a, p), v in zip(rows, _vectors(articles), strict=True)
    ]
    return days, since, points


def kmeans(x: np.ndarray, k: int) -> np.ndarray:
    """Cluster labels for each row of ``x``: k-means++ init from ``SEED``."""
    rng = np.random.default_rng(SEED)
    n = len(x)
    centres = [x[rng.integers(n)]]
    for _ in range(1, k):
        d2 = np.min(((x[:, None, :] - np.array(centres)[None]) ** 2).sum(-1), axis=1)
        total = d2.sum()
        # Every point already sits on a centre: the rest are duplicates.
        pick = rng.integers(n) if total == 0 else rng.choice(n, p=d2 / total)
        centres.append(x[pick])
    c = np.array(centres)

    labels = np.full(n, -1)
    for _ in range(KMEANS_ITERATIONS):
        new = ((x[:, None, :] - c[None]) ** 2).sum(-1).argmin(axis=1)
        if np.array_equal(new, labels):
            break
        labels = new
        for j in range(k):
            members = x[labels == j]
            if len(members):
                c[j] = members.mean(axis=0)
    return labels


def fold_small(x: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Move the points of each cluster under ``MIN_CLUSTER`` to the nearest
    other centroid, smallest first, then renumber clusters largest first."""
    labels = labels.copy()
    while True:
        sizes = Counter(labels.tolist())
        if len(sizes) <= 1:
            break
        small = min(sizes, key=lambda j: (sizes[j], j))
        if sizes[small] >= MIN_CLUSTER:
            break
        others = sorted(j for j in sizes if j != small)
        centres = np.array([x[labels == j].mean(axis=0) for j in others])
        for i in np.flatnonzero(labels == small):
            labels[i] = others[int(((centres - x[i]) ** 2).sum(-1).argmin())]

    sizes = Counter(labels.tolist())
    order = sorted(sizes, key=lambda j: (-sizes[j], j))
    renumber = {old: new for new, old in enumerate(order)}
    return np.array([renumber[j] for j in labels.tolist()])


def _pca2(x: np.ndarray) -> np.ndarray:
    """Rows of ``x`` projected on their top two principal axes, with each
    axis's sign fixed so the result does not depend on the SVD's choice."""
    if len(x) < 2:
        return np.zeros((len(x), 2))
    centred = x - x.mean(axis=0)
    _, _, vt = np.linalg.svd(centred, full_matrices=False)
    axes = vt[:2]
    for i, axis in enumerate(axes):
        if axis[np.abs(axis).argmax()] < 0:
            axes[i] = -axis
    return centred @ axes.T


def _scale(values: np.ndarray, low: float, high: float) -> np.ndarray:
    span = values.max() - values.min()
    if span < 1e-12:
        return np.full_like(values, (low + high) / 2)
    return low + (values - values.min()) / span * (high - low)


def spread_apart(centres: np.ndarray) -> np.ndarray:
    """Push centres closer than ``MIN_GAP`` apart, inside the centre band."""
    c = centres.copy()
    m = len(c)
    for _ in range(SPREAD_ITERATIONS):
        moved = False
        for i in range(m):
            for j in range(i + 1, m):
                d = c[j] - c[i]
                dist = float(np.linalg.norm(d))
                if dist >= MIN_GAP:
                    continue
                # Two centres on one spot: split them along a fixed direction.
                unit = d / dist if dist > 1e-9 else np.array([1.0, 0.0])
                step = (MIN_GAP - dist) / 2 * unit
                c[i] -= step
                c[j] += step
                moved = True
        c = np.clip(c, CENTRE_LOW, CENTRE_HIGH)
        if not moved:
            break
    return c


def layout(x: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(centres, points)``, both as 0..1 coordinates. Centres come from a PCA
    of the centroids; each point sits around its centre by its cluster's own
    PCA, drawn larger for a looser cluster."""
    m = int(labels.max()) + 1
    centroids = np.array([x[labels == j].mean(axis=0) for j in range(m)])
    flat = _pca2(centroids)
    centres = spread_apart(
        np.column_stack([_scale(flat[:, i], CENTRE_LOW, CENTRE_HIGH) for i in range(2)])
    )

    spread = np.array(
        [np.linalg.norm(x[labels == j] - centroids[j], axis=1).mean() for j in range(m)]
    )
    widest = spread.max() or 1.0
    points = np.zeros((len(x), 2))
    for j in range(m):
        idx = np.flatnonzero(labels == j)
        local = _pca2(x[idx])
        reach = np.linalg.norm(local, axis=1).max()
        if reach > 1e-12:
            local = local / reach
        radius = CLUSTER_RADIUS * (0.5 + 0.5 * spread[j] / widest)
        points[idx] = centres[j] + local * radius
    return centres, np.clip(points, 0.0, 1.0)


def cluster_labels(tags: list[list[str]], labels: np.ndarray) -> list[str]:
    """One label per cluster: its tags by lift (share in the cluster over share
    overall), so a tag on every article never names one. A tag already naming
    a larger cluster is skipped."""
    n = len(tags)
    overall = Counter(t for ts in tags for t in set(ts))
    used: set[str] = set()
    out: list[str] = []
    for j in range(int(labels.max()) + 1):
        members = [tags[i] for i in np.flatnonzero(labels == j)]
        inside = Counter(t for ts in members for t in set(ts))
        lift = {
            t: (c / len(members)) / (overall[t] / n)
            for t, c in inside.items()
            if c >= MIN_TAG_COUNT
        }
        ranked = [
            t
            for t in sorted(lift, key=lambda t: (-lift[t], -inside[t], t))
            if lift[t] > 1 and t not in used
        ]
        if not ranked:
            out.append(FALLBACK_LABEL)
            continue
        label = ranked[0]
        if len(ranked) > 1 and len(f"{label} · {ranked[1]}") <= LABEL_CHARS:
            label = f"{label} · {ranked[1]}"
        used.add(ranked[0])
        out.append(label)
    return out


def build(points: list[Point], days: int, since: datetime, now: datetime) -> TopicMap:
    """The file's contents. Pure."""
    data: TopicMap = {
        "v": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "window_days": days,
        "since": since.isoformat(),
        "count": len(points),
        "clusters": [],
        "points": [],
    }
    if not points:
        return data

    x = np.array([p.vector for p in points], dtype=np.float64)
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    x = x / np.where(norms == 0, 1.0, norms)

    labels = fold_small(x, kmeans(x, cluster_count(len(points))))
    centres, xy = layout(x, labels)
    names = cluster_labels([p.tags for p in points], labels)
    sizes = Counter(labels.tolist())

    data["clusters"] = [
        {
            "id": j,
            "label": names[j],
            "x": round(float(centres[j, 0]), 4),
            "y": round(float(centres[j, 1]), 4),
            "size": sizes[j],
        }
        for j in range(len(names))
    ]
    data["points"] = [
        {
            "id": p.id,
            "x": round(float(xy[i, 0]), 4),
            "y": round(float(xy[i, 1]), 4),
            "cluster": int(labels[i]),
            "score": p.score,
            "title": p.title,
            "url": p.url,
            "publisher": p.publisher,
        }
        for i, p in enumerate(points)
    ]
    return data


def write_atomic(path: Path, data: TopicMap) -> None:
    """Write to a temp file beside ``path``, then rename over it, so a reader
    never sees half a file and a failed run leaves the last good one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        # mkstemp makes the file 0600; Caddy reads it as another user.
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def output_path() -> Path:
    return Path(os.environ.get("TOPIC_MAP_PATH") or DEFAULT_PATH)


if __name__ == "__main__":
    try:
        now = datetime.now(UTC)
        with Session(get_engine()) as session:
            days, since, points = read_points(session, now)
        data = build(points, days, since, now)
        write_atomic(output_path(), data)
        log(
            f"Topic map: {days}-day window, {data['count']} articles, "
            f"k={len(data['clusters'])}"
        )
    except Exception as e:
        print(f"Topic map failed: {e}", file=sys.stderr)
        sys.exit(1)
