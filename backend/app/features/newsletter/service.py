"""The weekly newsletter: who it goes to, and what it draws on - the week's
most talked-about topics and the articles readers liked.

The curation agent already read and scored every article, so nothing here
judges. `week` groups the week into topics and ranks them by how many
publishers carried them; `liked` lists what readers liked.

Popularity counts the ledger too. Curation approves one copy of a story and
rejects the rest as retellings, so the feed alone says every story was carried
once; the rejects are where the other outlets are.

The maths is curation's (`app.core.embedding`): one topic is rows within
`DEDUP_DIST_THRESHOLD` of a published article.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta

import numpy as np
import resend
from sqlmodel import Session, col, func, select

from app.core.db.article import Article
from app.core.db.ledger import Reject
from app.core.db.like import ArticleLike, like_counts_subquery
from app.core.db.publisher import Publisher
from app.core.db.subscriber import NewsletterSubscriber
from app.core.embedding import (
    DEDUP_DIST_THRESHOLD,
    SNIPPET_CAP,
    cosine_distances,
    embed_batch,
    story_groups,
    to_embedding_text,
)
from app.features.newsletter.broadcast import draft as draft
from app.features.newsletter.model import (
    CoveredBy,
    LikedArticle,
    WeekArticle,
    WeekTopic,
)
from app.features.newsletter.topics import TOPICS as TOPICS
from app.features.newsletter.topics import create_missing as create_missing

# The skill asks for more than the 10-12 links it picks, so it can pass over
# what has no value for builders.
WEEK_LIMIT = 40

logger = logging.getLogger(__name__)


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


def liked(
    session: Session, days: int = 7, now: datetime | None = None
) -> list[LikedArticle]:
    """Articles readers liked in the last ``days``, however old the article,
    the most likes in the window first, then the highest score."""
    since = (now or datetime.now(UTC)) - timedelta(days=days)
    likes = func.count().label("likes")
    rows = session.exec(
        select(Article, Publisher, likes)
        .join(ArticleLike, col(ArticleLike.article_id) == col(Article.id))
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .where(
            col(ArticleLike.created_at) >= since,
            col(Article.marked_for_deletion_at).is_(None),
        )
        .group_by(col(Article.id), col(Publisher.id))
        .order_by(likes.desc(), col(Article.score).desc())
    ).all()
    return [
        {
            "url": a.url,
            "title": a.title,
            "publisher": p.name,
            "publisher_kind": str(p.kind),
            "kind": str(a.kind),
            "score": a.score,
            "likes": int(n),
            "summary": a.summary or "",
            "published_at": a.published_at.date().isoformat() if a.published_at else "",
        }
        for a, p, n in rows
    ]


def subscribe(*, session: Session, email: str, utm_source: str | None = None) -> None:
    """Add an email to the newsletter. An address already on it is left as is."""
    if session.get(NewsletterSubscriber, email) is None:
        session.add(NewsletterSubscriber(email=email, utm_source=utm_source))
        session.commit()

    api_key = os.getenv("RESEND_API_KEY")
    audience_id = os.getenv("RESEND_AUDIENCE_ID")
    if api_key and audience_id:
        resend.api_key = api_key
        try:
            resend.Contacts.create({"email": email, "audience_id": audience_id})
        except Exception as e:
            if "already exists" not in str(e):
                logger.error(f"Resend contact create failed for {email}: {e}")
