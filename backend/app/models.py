import re
import unicodedata
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from pydantic import EmailStr
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


# ─── User ────────────────────────────────────────────────────────────────────


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


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


class FeedItemStatus(StrEnum):
    """Where a feed item sits in the curation agent's loop.

    The agent is non-deterministic and its runs can die halfway, so a run only
    ever picks up `new` rows — anything already decided is never reconsidered.
    """

    new = "new"
    accepted = "accepted"
    rejected = "rejected"


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


# ─── FeedItem ──────────────────────────────────────────────────────────────


class FeedItemBase(SQLModel):
    """One item a source emitted, stored with no judgment applied.

    This is the curation agent's inbox. The pipeline that fills it does no
    scoring, no categorizing and no content re-fetching — rows are thin on
    purpose, and the agent fetches what it decides it needs. An accepted item
    becomes an `article`; the feed item itself is kept as the audit trail and
    pruned after 30 days.
    """

    # the item's identity: the pipeline skips a URL already in `feed_item` or
    # `article`, so the same story never lands in the inbox twice.
    url: str = Field(unique=True, index=True)
    title: str
    # feed-embedded text. Often empty (HN links, AI News recaps) — an empty
    # content is a normal row, not a broken one.
    content: str | None = None
    published_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    # who *carried* the item, which is not necessarily who wrote it: HN and AI
    # News are carriers. Resolving the first-party publisher is the agent's job.
    feed_publisher_id: int | None = Field(default=None, foreign_key="publisher.id")
    # pre-parsed outbound candidates, best-first: [{url, host, kind, text}].
    # Only AI News fills this; everywhere else it is empty.
    links: list[dict] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )


class FeedItem(FeedItemBase, table=True):
    __tablename__ = "feed_item"
    id: int | None = Field(default=None, primary_key=True)
    fetched_at: datetime = Field(
        default_factory=get_datetime_utc,
        index=True,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    status: FeedItemStatus = Field(default=FeedItemStatus.new, index=True)
    # the agent's one-line reason for the decision
    decision: str | None = None
    decided_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


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
    # per-publisher fetch/insert counts within the "Feeds" source: [{name, fetched, inserted, error}]
    publishers: list[dict] = Field(
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


# ─── Agent tool API ────────────────────────────────────────────────────────
# Request/response shapes for /api/v1/agent/*, the curation agent's toolbox.
# Reads are wide (the agent decides what it needs); writes are typed, one shape
# per thing it is allowed to create.


class FeedItemPublic(FeedItemBase):
    id: int
    fetched_at: datetime
    status: FeedItemStatus
    decision: str | None = None
    # the carrier's display name, so triaging a batch needs no second lookup
    feed_publisher: str | None = None
    # content is clipped on the way out (see the `content_chars` query param):
    # a full Substack post is tens of thousands of characters and a batch of
    # them would swallow the agent's context before it judged anything.
    content_truncated: bool = False


class FeedItemsPublic(SQLModel):
    data: list[FeedItemPublic]
    count: int


class FeedItemDecision(SQLModel):
    status: FeedItemStatus
    decision: str = Field(max_length=500)


class AgentPublisher(SQLModel):
    id: int
    slug: str
    name: str
    kind: PublisherKind
    type: PublisherType
    trust: TrustLevel
    is_active: bool
    description: str | None = None
    links: dict[LinkPlatform, str] = Field(default_factory=dict)


class PublisherUpsert(SQLModel):
    slug: str
    name: str
    kind: PublisherKind
    type: PublisherType = PublisherType.other
    description: str | None = None
    image: str | None = None
    links: dict[LinkPlatform, str] = Field(default_factory=dict)
    trust: TrustLevel = TrustLevel.medium
    # A publisher with is_active=true and no rss/substack link is an
    # attribution target the pipeline never polls — which is exactly what a
    # first-party source discovered mid-run should be.
    is_active: bool = True


class AgentTag(SQLModel):
    id: int
    slug: str
    name: str
    description: str | None = None


class TagCreate(SQLModel):
    slug: str
    name: str
    description: str | None = None


class SqlReadRequest(SQLModel):
    query: str
    limit: int | None = Field(default=None, ge=1)


class SqlReadResult(SQLModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool


class FetchUrlRequest(SQLModel):
    url: str


class FetchUrlResult(SQLModel):
    url: str
    # false means "nothing readable came back" — a 403, a paywall, a JS-only
    # page, or a host we skip. Not an error: the agent judges on what it has.
    ok: bool
    chars: int
    text: str
    truncated: bool


class AgentArticleCreate(SQLModel):
    url: str
    title: str
    # the *first-party* publisher, not whoever carried the item. Must already
    # exist — mint it with upsert_publisher first if it doesn't.
    publisher_slug: str
    score: int = Field(ge=1, le=100)
    kind: ArticleKind = ArticleKind.blog
    categories: list[Category] = Field(default_factory=list)
    summary: str | None = None
    content: str | None = None
    published_at: datetime | None = None
    # slugs from the controlled vocabulary; unknown ones are rejected, never
    # silently dropped, so a typo is visible instead of costing the tag.
    tags: list[str] = Field(default_factory=list)


class AgentArticleCreated(SQLModel):
    id: int
    url: str
    title: str
    score: int
    publisher_slug: str
    tags: list[str]
    # false means the article was stored without a vector: it will not show up
    # in `/articles/search`, so a later dedup check cannot see it.
    embedded: bool
