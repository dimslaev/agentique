"""The controlled category vocabulary (loaded from the DB), its prototype
vectors, and validation for MatchCategories.

The vocabulary is the `category` table — slug, display name, the "what belongs
here" description fed to the LLM, and the exemplar phrases the static
pre-filter's prototype vector is built from. Nothing is hardcoded here: adding
or rewording a category is a DB change (see `app/seed_categories.py`).

Prototypes are computed per run rather than stored. Seven encodes of a static
model cost nothing, and a stored vector could silently go stale against an
edited description — the failure mode where a category quietly stops matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlmodel import Session, col, select

from app.models import ArticleCategory, Category
from pipeline.embedding import embed_batch
from pipeline.utils import enum_value, log

# An article may carry at most this many categories. Measured on the prod dump,
# the cap almost never binds — 52 of 877 articles reached 3 — so it is a guard
# against a model that pads, not a routine constraint.
MAX_CATEGORIES_PER_ARTICLE = 3


# eq=False because `prototypes` is a numpy array: the generated __eq__ would
# return an array rather than a bool, and frozen's __hash__ would raise on it.
# Nothing compares or hashes a Vocabulary, and this keeps it that way.
@dataclass(frozen=True, eq=False)
class Vocabulary:
    """The controlled category set for one pipeline run, plus the prototype
    matrix the static gate scores against.

    ``prototypes`` is (n_categories, 256), L2-normalised, row *i* matching
    ``slugs_ordered[i]``.
    """

    slug_to_id: dict[str, int]
    slug_to_name: dict[str, str]
    slug_to_description: dict[str, str]
    slugs_ordered: tuple[str, ...]
    prototypes: np.ndarray

    @property
    def slugs(self) -> frozenset[str]:
        return frozenset(self.slug_to_id)


def _prototype_text(name: str, description: str, exemplars: list[str]) -> str:
    """One string per category, embedded into its prototype vector.

    Name and description carry the category's own words; the exemplars pull the
    prototype toward how articles about it are actually phrased. Both matter —
    a description alone reads like a definition, and article titles do not.
    """
    parts = [name, description, *exemplars]
    return "\n".join(p.strip() for p in parts if p and p.strip())


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1.0, norms)


def load_vocabulary(session: Session) -> Vocabulary:
    """Read the active categories once per run and build their prototypes.

    Raises if empty — an unseeded vocabulary would match nothing, and the
    pipeline would silently stop storing articles altogether. Failing loudly
    beats a night of zero inserts.
    """
    rows = session.exec(
        select(Category)
        .where(col(Category.is_active).is_(True))
        .order_by(col(Category.position), col(Category.id))
    ).all()
    if not rows:
        raise RuntimeError(
            "category table is empty — the controlled vocabulary must be seeded "
            "first (python -m app.seed_categories)"
        )

    usable = [c for c in rows if c.id is not None]
    texts = [_prototype_text(c.name, c.description, list(c.exemplars)) for c in usable]
    prototypes = _normalize_rows(np.array(embed_batch(texts), dtype=np.float32))

    return Vocabulary(
        slug_to_id={c.slug: c.id for c in usable if c.id is not None},
        slug_to_name={c.slug: c.name for c in usable},
        slug_to_description={c.slug: c.description for c in usable},
        slugs_ordered=tuple(c.slug for c in usable),
        prototypes=prototypes,
    )


def normalize_category(raw: Any, valid: frozenset[str]) -> str | None:
    """Coerce a returned category to a canonical slug, or None if it's off-list.

    The model returns plain strings, but tolerate stray casing, underscores and
    ampersands ("Tool Use & MCP" -> "tool-use-mcp") before validating against
    the vocabulary.
    """
    if raw is None:
        return None
    slug = enum_value(raw).strip().lower().replace("&", "").replace("_", "-")
    slug = "-".join(part for part in slug.replace(" ", "-").split("-") if part)
    return slug if slug in valid else None


def validate_categories(raw: list[Any], valid: frozenset[str]) -> list[str]:
    """Off-list output is dropped and nothing is minted at runtime. Order is
    preserved (the prompt asks for most-relevant-first) and duplicates removed,
    then the list is capped."""
    out: list[str] = []
    for item in raw:
        slug = normalize_category(item, valid)
        if slug is None:
            log(f"  Dropped off-list category {enum_value(item)!r}")
            continue
        if slug not in out:
            out.append(slug)
    return out[:MAX_CATEGORIES_PER_ARTICLE]


def write_article_categories(
    session: Session, article_id: int, slugs: list[str], vocab: Vocabulary
) -> None:
    """Write the join rows for one article. Uses merge so a re-run of the
    backfill over an already-categorised article is a no-op rather than a
    duplicate-key error."""
    for slug in slugs:
        category_id = vocab.slug_to_id.get(slug)
        if category_id is None:
            continue
        session.merge(ArticleCategory(article_id=article_id, category_id=category_id))
