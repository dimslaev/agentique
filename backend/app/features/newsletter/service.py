"""The weekly newsletter: who it goes to, and what it draws on - the week's
articles and the ones readers liked.

The curation agent already read and scored every article, and the newsletter
agent groups them by reading, so nothing here judges.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta

import resend
from sqlmodel import Session, col, func, select

from app.core.db.article import Article
from app.core.db.like import ArticleLike, like_counts_subquery
from app.core.db.publisher import Publisher
from app.core.db.subscriber import NewsletterSubscriber
from app.features.newsletter.broadcast import draft as draft
from app.features.newsletter.model import LikedArticle, WeekArticle
from app.features.newsletter.topics import TOPICS as TOPICS
from app.features.newsletter.topics import create_missing as create_missing

logger = logging.getLogger(__name__)


def get_last_week_articles(
    session: Session, days: int = 7, now: datetime | None = None
) -> list[WeekArticle]:
    """Every article published in the last ``days``, the most liked first,
    then the highest score."""
    since = (now or datetime.now(UTC)) - timedelta(days=days)
    likes = like_counts_subquery()
    like_count = func.coalesce(likes.c.like_count, 0)
    rows = session.exec(
        select(Article, Publisher, like_count)
        .join(Publisher, col(Publisher.id) == col(Article.publisher_id))
        .outerjoin(likes, likes.c.article_id == Article.id)
        .where(
            col(Article.created_at) >= since,
            col(Article.marked_for_deletion_at).is_(None),
        )
        .order_by(like_count.desc(), col(Article.score).desc())
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
        }
        for a, p, n in rows
    ]


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
