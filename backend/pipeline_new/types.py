"""The one object the pipeline carries from fetched to processed.

Rather than a chain of TypedDicts keyed by fragile string literals, a single
mutable dataclass accumulates fields as it moves through the stages. Every
field has a safe default for the stages that have not run yet, so a partially
processed article is always a valid object — never a dict missing a key.

Lifecycle of the fields:

    fetch   -> url, title, content, published_date, publisher_id, source, trust
    score   -> score
    persist -> id
    enrich  -> summary, categories, kind, tags   (content may be refetched)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import ArticleKind, Category, TrustLevel


@dataclass
class FeedPublisher:
    """An active RSS/substack publisher to poll. Carries everything the fetch
    needs to stamp an article's provenance, so there is no resolve-by-name step
    and no quarantine path: we only ever iterate publishers we already know."""

    id: int
    name: str
    rss_url: str
    trust: TrustLevel


@dataclass
class PipelineArticle:
    """One article flowing through the pipeline. See module docstring."""

    # ─ fetch ─
    url: str
    title: str
    content: str  # sanitized plain text from the feed; "" if the feed had none
    published_date: str  # raw feed date string; "" if absent
    publisher_id: int
    source: str  # publisher name, for prompts and logs
    trust: TrustLevel

    # ─ score ─
    score: int = 0

    # ─ persist ─
    id: int | None = None

    # ─ enrich ─
    summary: str = ""
    categories: list[Category] = field(default_factory=list)
    kind: ArticleKind | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def trust_tag(self) -> str:
        """The ``"high"|"medium"|"low"`` string the BAML prompts expect."""
        return self.trust.value
