import uuid
from datetime import UTC, datetime
from enum import Enum

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


class PublisherKind(str, Enum):
    individual = "individual"
    company = "company"
    community = "community"
    media = "media"


class TrustLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ArticleKind(str, Enum):
    blog = "blog"
    product = "product"
    announcement = "announcement"
    repo = "repo"
    paper = "paper"
    model = "model"


class Category(str, Enum):
    dev = "dev"
    models = "models"
    research = "research"


class Channel(str, Enum):
    rss = "rss"
    hackernews = "hackernews"
    newsletter = "newsletter"
    ainews = "ainews"


class LinkPlatform(str, Enum):
    website = "website"
    rss = "rss"
    twitter = "twitter"
    github = "github"
    substack = "substack"
    youtube = "youtube"
    linkedin = "linkedin"
    mastodon = "mastodon"
    discord = "discord"


# ─── Publisher ──────────────────────────────────────────────────────────


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
        sa_type=DateTime(timezone=True),
    )


# ─── Article ────────────────────────────────────────────────────────────


class ArticleBase(SQLModel):
    title: str
    url: str
    publisher_id: int = Field(foreign_key="publisher.id")
    published_at: datetime | None = None
    score: int
    kind: ArticleKind = ArticleKind.blog
    categories: list[Category] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    channel: Channel
    summary: str | None = None
    content: str | None = None


class Article(ArticleBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    embedding: list[float] | None = Field(
        default=None, sa_column=Column(Vector(256), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )


# ─── Tag ────────────────────────────────────────────────────────────────


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(unique=True)
    name: str


class ArticleTag(SQLModel, table=True):
    __tablename__ = "article_tag"
    article_id: int = Field(foreign_key="article.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)


# ─── ArticleLike ────────────────────────────────────────────────────────


class ArticleLike(SQLModel, table=True):
    __tablename__ = "article_like"
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    article_id: int = Field(foreign_key="article.id", primary_key=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
