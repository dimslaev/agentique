"""Catalog schema: publishers, articles, tags, and the read shapes the feed serves."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel

from app.platform.dates import get_datetime_utc


def slugify(name: str) -> str:
    """Publisher/tag slug: ASCII-fold, lowercase, non-alnum -> single hyphen.

    Used to map a fetched item's source name -> a Publisher.slug so the pipeline
    can look the publisher up (or auto-create it). Deterministic and stable.
    """
    ascii_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug


# ─── Enums (this module is the schema source of truth) ─────────────────────


class PublisherKind(StrEnum):
    individual = "individual"
    company = "company"
    community = "community"
    media = "media"


class PublisherType(StrEnum):
    """How the pipeline discovers a publisher's articles (its ingestion source)."""

    rss = "rss"
    substack = "substack"
    search = "search"
    hn = "hn"
    reddit = "reddit"
    email = "email"
    ainews = "ainews"
    other = "other"


class TrustLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class ArticleKind(StrEnum):
    blog = "blog"
    product = "product"
    announcement = "announcement"
    repo = "repo"
    paper = "paper"
    model = "model"


class Category(StrEnum):
    dev = "dev"
    models = "models"
    research = "research"


class LinkPlatform(StrEnum):
    website = "website"
    rss = "rss"
    # first-party domain to discover articles from via search, for labs that
    # publish no RSS feed (see pipeline.sources.lab_watch). Value is the bare
    # host, e.g. "anthropic.com".
    search = "search"
    twitter = "twitter"
    github = "github"
    substack = "substack"
    youtube = "youtube"
    linkedin = "linkedin"
    mastodon = "mastodon"
    discord = "discord"
    email = "email"


# ─── Publisher ─────────────────────────────────────────────────────────────


class PublisherBase(SQLModel):
    slug: str
    name: str
    kind: PublisherKind
    type: PublisherType = PublisherType.other
    description: str | None = None
    image: str | None = None
    links: dict[LinkPlatform, str] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    trust: TrustLevel = TrustLevel.medium
    is_active: bool = True


class Publisher(PublisherBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # Broad publishers (a general engineering blog, not an AI one) that post
    # mostly off-topic. When set, the fetch step drops anything whose title
    # fails the topic gate before it costs an embedding or an LLM call —
    # see pipeline.steps.fetch.drop_off_topic. Deliberately not on
    # PublisherBase: this is ingestion policy, not part of the public read API.
    topic_gated: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# ─── Article ───────────────────────────────────────────────────────────────


class ArticleBase(SQLModel):
    title: str
    url: str
    publisher_id: int = Field(foreign_key="publisher.id")
    published_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    score: int
    kind: ArticleKind = ArticleKind.blog
    categories: list[Category] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    summary: str | None = None
    content: str | None = None


class Article(ArticleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    # 256-dim model2vec vectors; nullable until the import script runs
    embedding: list[float] | None = Field(
        default=None, sa_column=Column(Vector(256), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# ─── Tag ───────────────────────────────────────────────────────────────────


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True)
    name: str
    # "when to apply this tag" — fed to the AssignTags prompt as the vocabulary
    description: str | None = None


class ArticleTag(SQLModel, table=True):
    __tablename__ = "article_tag"
    article_id: int = Field(foreign_key="article.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)


# ─── Read API shapes ───────────────────────────────────────────────────────
# Consumer-facing views. `publisher` is nested (replaces the old `source` string)
# and `tags` come from the article_tag join. Pipeline provenance and bulk fields
# (content, embedding, links, trust) stay internal.


class PublisherPublic(SQLModel):
    id: int
    slug: str
    name: str
    kind: PublisherKind
    image: str | None = None


class TagPublic(SQLModel):
    slug: str
    name: str


class ArticlePublic(SQLModel):
    id: int
    title: str
    url: str
    summary: str | None = None
    score: int
    kind: ArticleKind
    categories: list[Category] = Field(default_factory=list)
    published_at: datetime | None = None
    created_at: datetime | None = None
    publisher: PublisherPublic
    tags: list[TagPublic] = Field(default_factory=list)
    like_count: int = 0
    liked_by_me: bool = False


class ArticlesPublic(SQLModel):
    data: list[ArticlePublic]
    count: int


# ─── Facets (sidebar filter options) ───────────────────────────────────────


class PublisherFacet(SQLModel):
    slug: str
    name: str
    count: int


class TagFacet(SQLModel):
    slug: str
    name: str
    count: int


class ArticleFacets(SQLModel):
    publishers: list[PublisherFacet]
    tags: list[TagFacet]
