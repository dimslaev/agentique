"""The publisher table: who an article is credited to, and how its articles are found."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel

from app.core.dates import get_datetime_utc


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


class PublisherKind(StrEnum):
    # Makes models and posts about them on its own domain.
    lab = "lab"
    company = "company"
    individual = "individual"
    media = "media"
    # Aggregators (Hacker News, Reddit). Credited only for posts on their own
    # site; anything they link to is credited to its author.
    community = "community"
    # A publisher the pipeline created from a URL it had not seen. The curation
    # agent sets the real kind the first time it approves one of its articles.
    unknown = "unknown"


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
    # mostly off-topic. No longer read: the fetch step used to drop their
    # off-topic titles, and the curation agent judges topic now (ADR 11). The
    # column stays because deploy runs additive migrations only.
    topic_gated: bool = Field(default=False, nullable=False)
    # What the nightly run last saw of this publisher, written by
    # pipeline.runs: when its feed last answered, when it last gave us a new
    # candidate, and the error it last failed with (cleared by the next good
    # fetch). Ingestion bookkeeping, not on the public API.
    last_fetched_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_new_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    last_error: str | None = None
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
