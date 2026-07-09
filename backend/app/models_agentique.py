import re
import unicodedata
import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


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
    twitter = "twitter"
    github = "github"
    substack = "substack"
    youtube = "youtube"
    linkedin = "linkedin"
    mastodon = "mastodon"
    discord = "discord"


# ─── Publisher ─────────────────────────────────────────────────────────────


class PublisherBase(SQLModel):
    slug: str
    name: str
    kind: PublisherKind
    description: str | None = None
    image: str | None = None
    links: dict[LinkPlatform, str] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    trust: TrustLevel = TrustLevel.medium
    is_active: bool = True


class Publisher(PublisherBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
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


# ─── Read API shapes ───────────────────────────────────────────────────────
# Consumer-facing views. `publisher` is nested (replaces the old `source` /
# `source_type` strings) and `tags` come from the article_tag join. Pipeline
# provenance and bulk fields (content, embedding, links, trust) stay internal.


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


# ─── ArticleLike ─────────────────────────────────────────────────────────────


class ArticleLike(SQLModel, table=True):
    __tablename__ = "article_like"
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    article_id: int = Field(foreign_key="article.id", primary_key=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ScoredUrl(SQLModel, table=True):
    __tablename__ = "scored_url"
    url: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=get_datetime_utc)


class PipelineRun(SQLModel, table=True):
    """One row per nightly pipeline run — the numeric record the verifier reasons over."""

    __tablename__ = "pipeline_run"
    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    duration_ms: int | None = None
    ok: bool = Field(default=False)
    # per-source funnel counts: [{source, fetched, filtered_known, ..., inserted, errors}]
    sources: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )


class AnalyticsEvent(SQLModel, table=True):
    """First-party analytics event — one row per pageview or custom event.

    No dashboard by design: query the `analytics_event` table directly with SQL.
    """

    __tablename__ = "analytics_event"
    id: int | None = Field(default=None, primary_key=True)
    event: str = Field(default="pageview", index=True)
    path: str | None = Field(default=None, index=True)
    referrer: str | None = None
    # anonymous client id persisted in the browser (localStorage), not a cookie
    visitor_id: str | None = Field(default=None, index=True)
    # set only when the request carries a valid bearer token
    user_id: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    user_agent: str | None = None
    # arbitrary metadata for custom events
    props: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        index=True,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class AnalyticsEventCreate(SQLModel):
    event: str = "pageview"
    path: str | None = None
    referrer: str | None = None
    visitor_id: str | None = None
    props: dict = Field(default_factory=dict)


class NewsletterSubscriber(SQLModel, table=True):
    __tablename__ = "newsletter_subscriber"
    email: str = Field(primary_key=True)
    categories: list[str] = Field(
        default_factory=lambda: ["all"], sa_column=Column(JSON, nullable=False)
    )
    custom_category: str = Field(default="")
    utm_source: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=get_datetime_utc)
    updated_at: datetime = Field(default_factory=get_datetime_utc)


class NewsletterSubscribeRequest(SQLModel):
    email: str
    categories: list[str] = Field(default_factory=lambda: ["all"])
    customCategory: str = ""
    utm_source: str | None = None


class NewsletterSubscribeResponse(SQLModel):
    ok: bool = True
