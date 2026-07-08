"""Controlled tag vocabulary (loaded from the DB) + validation for AssignTags.

The vocabulary is the `tag` table — slug, display name, and the "when to apply
this" description that gets fed to the LLM. Nothing is hardcoded here: adding or
renaming a tag is a DB change. We still post-validate the LLM output against the
loaded slug set and drop anything off-list, and we never mint tags at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from app.models_agentique import ArticleTag, Tag
from pipeline.utils import log

MAX_TAGS_PER_ARTICLE = 3


@dataclass(frozen=True)
class Vocabulary:
    """The controlled tag set for one pipeline run."""

    slug_to_id: dict[str, int]
    slug_to_description: dict[str, str]

    @property
    def slugs(self) -> frozenset[str]:
        return frozenset(self.slug_to_id)


def load_vocabulary(session: Session) -> Vocabulary:
    """Read the whole `tag` table once per run.

    Raises if it's empty — an unseeded vocabulary would silently tag nothing,
    which is worse than failing loudly.
    """
    rows = session.exec(select(Tag)).all()
    if not rows:
        raise RuntimeError(
            "tag table is empty — the controlled vocabulary must be seeded first"
        )
    return Vocabulary(
        slug_to_id={t.slug: t.id for t in rows if t.id is not None},
        slug_to_description={t.slug: t.description or "" for t in rows},
    )


def normalize_tag(raw: Any, valid: frozenset[str]) -> str | None:
    """Coerce a returned tag to a canonical slug, or None if it's off-list.

    The model returns plain strings now, but tolerate stray casing/underscores
    before validating against the vocabulary.
    """
    if raw is None:
        return None
    value = getattr(raw, "value", raw)  # tolerate an enum-ish value
    slug = str(value).strip().lower().replace("_", "-")
    return slug if slug in valid else None


def validate_tags(raw_tags: list[Any], valid: frozenset[str]) -> list[str]:
    """Normalize, drop off-list, dedupe (order-preserving), cap at 3."""
    seen: dict[str, None] = {}
    for raw in raw_tags:
        slug = normalize_tag(raw, valid)
        if slug and slug not in seen:
            seen[slug] = None
    return list(seen)[:MAX_TAGS_PER_ARTICLE]


def write_article_tags(
    session: Session,
    article_id: int,
    slugs: list[str],
    vocab: Vocabulary,
) -> None:
    """Write ArticleTag rows for one article. Slugs are guaranteed to be in the
    vocabulary (validate_tags drops anything else), so we only ever look up —
    never create. Idempotent-ish: skips (article, tag) pairs already present so
    re-runs don't error on the composite PK."""
    if not slugs:
        return
    existing = set(
        session.exec(
            select(ArticleTag.tag_id).where(ArticleTag.article_id == article_id)
        ).all()
    )
    for slug in slugs:
        tag_id = vocab.slug_to_id[slug]
        if tag_id not in existing:
            session.add(ArticleTag(article_id=article_id, tag_id=tag_id))
            existing.add(tag_id)
    log(f"    Tagged #{article_id}: {', '.join(slugs)}")
