"""The article table, its kind, and the kind a URL's host settles on its own."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import JSON, Column, DateTime, Index
from sqlmodel import Field, SQLModel

from app.core.dates import get_datetime_utc
from app.core.urls import hostname


class ArticleKind(StrEnum):
    # A blog post, launch post or announcement: what kind of post it is follows
    # from who published it (PublisherKind), not from a label on the article.
    post = "post"
    repo = "repo"
    paper = "paper"
    model = "model"


# No longer written: `dev` covered most of the feed, and publisher kind plus
# article kind split it better. The column stays because deploy runs additive
# migrations only.
class Category(StrEnum):
    dev = "dev"
    models = "models"
    research = "research"


class ArticleBase(SQLModel):
    title: str
    url: str
    publisher_id: int = Field(foreign_key="publisher.id")
    published_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    score: int
    kind: ArticleKind = ArticleKind.post
    categories: list[Category] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    summary: str | None = None
    content: str | None = None


class Article(ArticleBase, table=True):
    __table_args__ = (
        Index("ix_article_score", "score"),
        Index("ix_article_published_at", "published_at"),
        Index(
            "ix_article_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    id: int | None = Field(default=None, primary_key=True)
    # 256-dim model2vec vectors; nullable until the import script runs
    embedding: list[float] | None = Field(
        default=None, sa_column=Column(Vector(256), nullable=True)
    )
    # The judge's one-sentence account of `score`. Internal, not on the public
    # API; null for articles scored before the scorer gave one.
    score_reason: str | None = None
    # The aggregator that found the link (Hacker News, a newsletter), when that
    # is not the publisher itself. Null for an article from its publisher's feed.
    found_via: str | None = None
    # Set by the retired rescore script (removed with the LLM scorer): when this
    # row was last rescored, and whether that rescore put it under the old
    # threshold. Marking only; nothing deletes a marked row automatically.
    rescored_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    marked_for_deletion_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


def kind_from_url(url: str) -> ArticleKind | None:
    """ArticleKind from a URL's host, or None if the host does not settle it.

    A github.com link is a repo and an arxiv.org link is a paper whatever the
    text says, so the host is asked first.
    """
    host = hostname(url)
    if host in ("github.com", "gitlab.com"):
        return ArticleKind.repo
    if host in ("huggingface.co", "hf.co"):
        return ArticleKind.model
    if host in ("arxiv.org", "ar5iv.labs.arxiv.org"):
        return ArticleKind.paper
    return None
