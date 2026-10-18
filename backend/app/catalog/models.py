"""The read shapes the feed serves: articles, facets, origins, voices and stories."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel

from app.core.db.article import ArticleKind
from app.core.db.publisher import PublisherKind


class Origin(StrEnum):
    """The feed's "From" filter: what the article is when that is settled (a
    repo, a paper, a model), otherwise who published it. Not stored; each
    article falls under exactly one, see `catalog.articles.origin_condition`."""

    lab = "lab"
    company = "company"
    individual = "individual"
    media = "media"
    repo = "repo"
    paper = "paper"
    model = "model"


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
    found_via: str | None = None
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


# ─── Origin counts (the left rail's "Who wrote this week") ─────────────────


class OriginCount(SQLModel):
    origin: Origin
    count: int


class FoundViaCount(SQLModel):
    # Null: the publisher's own feed.
    name: str | None
    count: int


class OriginCounts(SQLModel):
    since: datetime
    total: int
    origins: list[OriginCount]
    # Posts by a publisher still `unknown`: under no origin until curation
    # names its kind.
    unlabelled: int
    found_via: list[FoundViaCount]


# ─── Voices (the left rail's "Voices") ─────────────────────────────────────


class VoiceKind(StrEnum):
    """The Voices panel's tabs: Writers, Labs, Companies."""

    individual = "individual"
    lab = "lab"
    company = "company"


class VoiceArticle(SQLModel):
    title: str
    url: str
    score: int
    published_at: datetime | None = None


class Voice(SQLModel):
    slug: str
    name: str
    count: int
    # Oldest first, the last `facets.VOICE_SCORES` of `count`.
    scores: list[int]
    best: VoiceArticle


# ─── Stories (right rail) ──────────────────────────────────────────────────


class StoryArticlePublic(SQLModel):
    id: int
    title: str
    url: str
    publisher: str
    published_at: datetime | None = None
    score: int


class StoryPublic(SQLModel):
    slug: str
    name: str
    blurb: str
    article_count: int
    publisher_count: int
    first_at: datetime | None = None
    last_at: datetime | None = None
    # An article joined it in the last 24 hours.
    grew_today: bool
    # Newest first, at most `stories.STORY_ARTICLES` of `article_count`.
    articles: list[StoryArticlePublic]
