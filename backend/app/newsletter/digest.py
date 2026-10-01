"""What the weekly newsletter draws on: the week's most talked-about topics,
and what else the feed and the ledger hold on each one.

The curation agent already read and scored every article, so nothing here
judges. `week` groups the week into topics and ranks them by how many
publishers carried them; `related` puts one topic beside everything close to it
over a longer window, so the newsletter agent can find the individual writer
who tried the thing, or the repo that builds on it.

Popularity counts the ledger too. Curation approves one copy of a story and
rejects the rest as retellings, so the feed alone says every story was carried
once; the rejects are where the other outlets are.

The maths is curation's (`pipeline.curation`): one topic is rows within
`DEDUP_DIST_THRESHOLD` of a published article, and related is out to
`RELATED_DIST`. A review of a release sits in between: close enough to be about
it, far enough not to be a retelling.
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

# The agent drafts three issues a week; the rest are there so it can pass over a
# topic it finds nothing to say about.
WEEK_LIMIT = 12
# Long enough to reach the review that came out two weeks after a release.
RELATED_DAYS = 30
RELATED_LIMIT = 12
# Under this a reject is out of scope or slop. Commentary lands above it, and
# how people took a thing is part of what the issue explains.
RELATED_MIN_SCORE = 35

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
    score: int
    likes: int
    summary: str


class CoveredBy(TypedDict):
    """A ledger row on the same story: another outlet's copy, usually rejected
    as a retelling."""

    url: str
    title: str
    publisher: str
    publisher_kind: str
    score: int | None
    reason: str


class WeekTopic(TypedDict):
    # Distinct publishers carrying it this week, the ledger's included.
    coverage: int
    publishers: list[str]
    likes: int
    top_score: int
    articles: list[WeekArticle]
    covered_by: list[CoveredBy]


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


def _ledger_text(row: Reject) -> str:
    return to_embedding_text(row.title or "", (row.content or "")[:SNIPPET_CAP])


def week(
    session: Session,
    days: int = 7,
    limit: int = WEEK_LIMIT,
    now: datetime | None = None,
) -> list[WeekTopic]:
    """The last ``days`` of published articles grouped into topics, with the
    ledger rows on the same story, most publishers first, then most likes, then
    highest score. Up to ``limit`` topics.

    Every topic has at least one published article, so a story only the
    rejects carried (off scope, or slop) never ranks.
    """
    since = (now or datetime.now(UTC)) - timedelta(days=days)
    likes = like_counts_subquery()
    feed = session.exec(
        select(Article, Publisher, func.coalesce(likes.c.like_count, 0))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(likes, likes.c.article_id == Article.id)
        .where(
            col(Article.created_at) >= since,
            col(Article.marked_for_deletion_at).is_(None),
        )
    ).all()
    if not feed:
        return []
    ledger = session.exec(
        select(Reject, Publisher)
        .join(Publisher, col(Publisher.id) == col(Reject.publisher_id), isouter=True)
        .where(col(Reject.created_at) >= since, col(Reject.title).is_not(None))
    ).all()

    vecs = np.array(
        _vectors([a for a, _, _ in feed])
        + embed_batch([_ledger_text(r) for r, _ in ledger]),
        dtype=np.float32,
    )
    # Anchored on the articles: an edge needs one at an end, so rejects never
    # join a topic through each other.
    anchors = [True] * len(feed) + [False] * len(ledger)
    groups = story_groups(cosine_distances(vecs, vecs), anchors, DEDUP_DIST_THRESHOLD)
    grouped = {i for g in groups for i in g}
    groups += [[i] for i in range(len(feed)) if i not in grouped]

    topics: list[WeekTopic] = []
    for group in groups:
        articles: list[WeekArticle] = []
        covered_by: list[CoveredBy] = []
        for i in group:
            if i < len(feed):
                a, p, n = feed[i]
                articles.append(
                    {
                        "url": a.url,
                        "title": a.title,
                        "publisher": p.name,
                        "publisher_kind": str(p.kind),
                        "kind": str(a.kind),
                        "score": a.score,
                        "likes": int(n),
                        "summary": a.summary or "",
                    }
                )
            else:
                r, rp = ledger[i - len(feed)]
                covered_by.append(
                    {
                        "url": r.url,
                        "title": r.title or "",
                        "publisher": rp.name if rp else "",
                        "publisher_kind": str(rp.kind) if rp else "",
                        "score": r.score,
                        "reason": r.reason or "",
                    }
                )
        articles.sort(key=lambda r: r["score"], reverse=True)
        publishers = sorted(
            {r["publisher"] for r in [*articles, *covered_by] if r["publisher"]}
        )
        topics.append(
            {
                "coverage": len(publishers),
                "publishers": publishers,
                "likes": sum(a["likes"] for a in articles),
                "top_score": articles[0]["score"],
                "articles": articles,
                "covered_by": covered_by,
            }
        )
    topics.sort(key=lambda t: (t["coverage"], t["likes"], t["top_score"]), reverse=True)
    return topics[:limit]


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
        [_ledger_text(r) for r, _ in ledger]
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
