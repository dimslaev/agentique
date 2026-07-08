"""Fixed tag vocabulary + validation for the AssignTags step.

The 29 slugs here are the whole controlled vocabulary — the BAML `TagSlug` enum
(baml_src/tags.baml) mirrors them. We still post-validate the LLM output against
this set and drop anything off-list, per the brief. `name` is the human label
written to the `Tag.name` column.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models_agentique import ArticleTag, Tag
from pipeline.utils import log

# slug -> display name. Slugs must exactly match the @alias values in tags.baml.
TAG_NAMES: dict[str, str] = {
    "agents": "Agents",
    "orchestration": "Orchestration",
    "tool-calling": "Tool Calling",
    "agent-memory": "Agent Memory",
    "context-optimization": "Context Optimization",
    "auditing": "Auditing",
    "coding-assistants": "Coding Assistants",
    "multimodal": "Multimodal",
    "model-releases": "Model Releases",
    "open-weights": "Open Weights",
    "fine-tuning": "Fine-Tuning",
    "rag": "RAG",
    "evaluation": "Evaluation",
    "prompt-engineering": "Prompt Engineering",
    "robotics": "Robotics",
    "sandboxing": "Sandboxing",
    "product-launches": "Product Launches",
    "enterprise-ai": "Enterprise AI",
    "local-ai": "Local AI",
    "distributed-training": "Distributed Training",
    "safety": "Safety",
    "security": "Security",
    "privacy": "Privacy",
    "inference-optimization": "Inference Optimization",
    "speculative-decoding": "Speculative Decoding",
    "quantization": "Quantization",
    "model-distillation": "Model Distillation",
    "cost-optimization": "Cost Optimization",
    "hardware": "Hardware",
}

TAG_SLUGS: frozenset[str] = frozenset(TAG_NAMES)

MAX_TAGS_PER_ARTICLE = 3


def normalize_tag(raw: Any) -> str | None:
    """Coerce a BAML `TagSlug` enum member (or raw string) to a canonical slug.

    BAML enum member names use underscores; the canonical slug uses hyphens.
    Accept either the aliased slug or the underscore member name/value, then
    validate against the vocabulary. Returns None for anything off-list.
    """
    if raw is None:
        return None
    # enum -> its .value; plain string passes through
    value = getattr(raw, "value", raw)
    slug = str(value).strip().lower().replace("_", "-")
    return slug if slug in TAG_SLUGS else None


def validate_tags(raw_tags: list[Any]) -> list[str]:
    """Normalize, drop off-list, dedupe (order-preserving), cap at 3."""
    seen: dict[str, None] = {}
    for raw in raw_tags:
        slug = normalize_tag(raw)
        if slug and slug not in seen:
            seen[slug] = None
    return list(seen)[:MAX_TAGS_PER_ARTICLE]


def get_or_create_tag(session: Session, slug: str, tag_cache: dict[str, int]) -> int:
    """Return the Tag.id for ``slug``, creating the row on first use. Cached
    per run so we hit the DB at most once per distinct tag."""
    cached = tag_cache.get(slug)
    if cached is not None:
        return cached

    tag = session.exec(select(Tag).where(Tag.slug == slug)).first()
    if tag is None:
        tag = Tag(slug=slug, name=TAG_NAMES.get(slug, slug))
        session.add(tag)
        session.commit()
        session.refresh(tag)

    assert tag.id is not None
    tag_cache[slug] = tag.id
    return tag.id


def write_article_tags(
    session: Session,
    article_id: int,
    slugs: list[str],
    tag_cache: dict[str, int],
) -> None:
    """Write ArticleTag rows for one article. Idempotent-ish: skips (article,
    tag) pairs already present so re-runs don't error on the composite PK."""
    if not slugs:
        return
    existing = set(
        session.exec(
            select(ArticleTag.tag_id).where(ArticleTag.article_id == article_id)
        ).all()
    )
    for slug in slugs:
        tag_id = get_or_create_tag(session, slug, tag_cache)
        if tag_id not in existing:
            session.add(ArticleTag(article_id=article_id, tag_id=tag_id))
            existing.add(tag_id)
    log(f"    Tagged #{article_id}: {', '.join(slugs)}")
