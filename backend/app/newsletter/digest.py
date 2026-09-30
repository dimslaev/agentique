"""What the weekly newsletter draws on: the week's stories, and what else the
feed and the ledger hold on the same subject.

The curation agent already read and scored every article, so nothing here
judges. `week` groups the week's articles into stories and ranks them; `related`
puts one story beside everything close to it, so the newsletter agent can find
an individual writer's review or a repo that builds on a release.

The maths is curation's (`pipeline.curation`): one story is rows within
`DEDUP_DIST_THRESHOLD` of each other, and related is out to `RELATED_DIST`. A
review of a release sits in between: close enough to be about it, far enough
not to be a retelling.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NotRequired, TypedDict

import numpy as np
from sqlmodel import Session, col, func, select

from app.catalog.articles import like_counts_subquery
from app.catalog.models import Article, Publisher
from pipeline.curation import (
    DEDUP_DIST_THRESHOLD,
    RELATED_DIST,
    cosine_distances,
    nearest,
    story_groups,
)
from pipeline.embedding import embed_batch, to_embedding_text
from pipeline.models import Reject, RejectStage
from pipeline.steps import SNIPPET_CAP
from pipeline.url_kind import kind_from_url

# Below this an article is not a story the newsletter leads with or lists as a
# quick hit, and a week of everything the agent approved is more than one
# reading pass holds.
WEEK_MIN_SCORE = 70
# Long enough to reach the review that came out two weeks after a release.
RELATED_DAYS = 30
RELATED_LIMIT = 12
# A reject under this was turned down on its own merits, not as a retelling of
# something the feed carried, so it is nothing to point a reader at.
RELATED_MIN_SCORE = 55

PUBLISHED = "published"
REJECTED = "rejected"


class DigestError(ValueError):
    """A request the agent can correct, returned as a message."""


class WeekArticle(TypedDict):
    url: str
    title: str
    publisher: str
    publisher_kind: str
    kind: str
    categories: list[str]
    score: int
    likes: int
    summary: str


class WeekStory(TypedDict):
    top_score: int
    # Distinct publishers carrying the story this week.
    coverage: int
    publishers: list[str]
    articles: list[WeekArticle]


class RelatedRow(TypedDict):
    url: str
    title: str
    publisher: str
    publisher_kind: str
    kind: str
    stage: str
    score: int | None
    distance: float
    # Published rows: what a reader sees under the title.
    summary: NotRequired[str]
    # Rejected rows: why curation turned it down, e.g. as a retelling.
    reason: NotRequired[str]


class Related(TypedDict):
    url: str
    title: str
    rows: list[RelatedRow]


def _vectors(articles: list[Article]) -> list[list[float]]:
    """Each article's stored embedding, or one made now from the same text."""
    missing = [a for a in articles if a.embedding is None]
    made = iter(
        embed_batch(
            [
                to_embedding_text(a.title, (a.content or "")[:SNIPPET_CAP])
                for a in missing
            ]
        )
    )
    # pgvector hands back a numpy array, and bool(array) raises.
    return [
        list(a.embedding) if a.embedding is not None else next(made) for a in articles
    ]


def week(
    session: Session,
    days: int = 7,
    min_score: int = WEEK_MIN_SCORE,
    now: datetime | None = None,
) -> list[WeekStory]:
    """The articles published in the last ``days`` scoring ``min_score`` or
    more, grouped into stories, highest score first and then widest coverage.

    Every article is in exactly one story; most stories are one article.
    """
    since = (now or datetime.now(UTC)) - timedelta(days=days)
    likes = like_counts_subquery()
    rows = session.exec(
        select(Article, Publisher, func.coalesce(likes.c.like_count, 0))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(likes, likes.c.article_id == Article.id)
        .where(
            col(Article.created_at) >= since,
            col(Article.score) >= min_score,
            col(Article.marked_for_deletion_at).is_(None),
        )
    ).all()
    if not rows:
        return []

    vecs = np.array(_vectors([a for a, _, _ in rows]), dtype=np.float32)
    groups = story_groups(
        cosine_distances(vecs, vecs), [True] * len(rows), DEDUP_DIST_THRESHOLD
    )
    grouped = {i for g in groups for i in g}
    groups += [[i] for i in range(len(rows)) if i not in grouped]

    stories: list[WeekStory] = []
    for group in groups:
        articles: list[WeekArticle] = [
            {
                "url": a.url,
                "title": a.title,
                "publisher": p.name,
                "publisher_kind": str(p.kind),
                "kind": str(a.kind),
                "categories": [str(c) for c in a.categories],
                "score": a.score,
                "likes": int(n),
                "summary": a.summary or "",
            }
            for a, p, n in (rows[i] for i in group)
        ]
        articles.sort(key=lambda r: r["score"], reverse=True)
        publishers = sorted({r["publisher"] for r in articles})
        stories.append(
            {
                "top_score": articles[0]["score"],
                "coverage": len(publishers),
                "publishers": publishers,
                "articles": articles,
            }
        )
    stories.sort(key=lambda s: (s["top_score"], s["coverage"]), reverse=True)
    return stories


def related(
    session: Session,
    url: str,
    days: int = RELATED_DAYS,
    limit: int = RELATED_LIMIT,
    now: datetime | None = None,
) -> Related:
    """What the feed and the ledger hold close to one published article.

    Reads every article created in the last ``days`` and every reject from the
    same window that scored ``RELATED_MIN_SCORE`` or more: a hands-on review
    of a release the feed already carried can have been turned down as a
    retelling and still be worth a reader's time. Up to ``limit`` rows within
    ``RELATED_DIST``, closest first.
    """
    target = session.exec(select(Article).where(col(Article.url) == url)).first()
    if target is None:
        raise DigestError(f"No published article for {url}")
    target_vec = np.array(_vectors([target])[0], dtype=np.float32)
    since = (now or datetime.now(UTC)) - timedelta(days=days)

    feed = session.exec(
        select(Article, Publisher)
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .where(
            col(Article.created_at) >= since,
            col(Article.url) != url,
            col(Article.marked_for_deletion_at).is_(None),
        )
    ).all()
    ledger = session.exec(
        select(Reject, Publisher)
        .join(Publisher, col(Publisher.id) == col(Reject.publisher_id), isouter=True)
        .where(
            col(Reject.stage) == RejectStage.below_threshold,
            col(Reject.score) >= RELATED_MIN_SCORE,
            col(Reject.created_at) >= since,
        )
    ).all()

    rows: list[RelatedRow] = []
    for a, p in feed:
        rows.append(
            {
                "url": a.url,
                "title": a.title,
                "publisher": p.name,
                "publisher_kind": str(p.kind),
                "kind": str(a.kind),
                "stage": PUBLISHED,
                "score": a.score,
                "distance": 0.0,
                "summary": a.summary or "",
            }
        )
    for r, p in ledger:
        rows.append(
            {
                "url": r.url,
                "title": r.title or "",
                "publisher": p.name if p else "",
                "publisher_kind": str(p.kind) if p else "",
                "kind": str(kind_from_url(r.url) or ""),
                "stage": REJECTED,
                "score": r.score,
                "distance": 0.0,
                "reason": r.reason or "",
            }
        )
    if not rows:
        return {"url": url, "title": target.title, "rows": []}

    vecs = _vectors([a for a, _ in feed]) + embed_batch(
        [
            to_embedding_text(r.title or "", (r.content or "")[:SNIPPET_CAP])
            for r, _ in ledger
        ]
    )
    distances = cosine_distances(target_vec[None, :], np.array(vecs, dtype=np.float32))[
        0
    ]
    listed: list[RelatedRow] = []
    for i in nearest(distances, RELATED_DIST, limit):
        row = rows[i]
        row["distance"] = round(float(distances[i]), 3)
        listed.append(row)
    return {"url": url, "title": target.title, "rows": listed}
