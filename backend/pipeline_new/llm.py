"""Sanitized wrappers around the BAML functions.

The point of this layer: no stage ever touches the raw model client. Each call
here converts to/from the pipeline's own types, maps BAML enums onto the schema
enums (dropping unknowns), and runs every free-text field through
``pipeline_new.text`` before it is returned. A call that raises is the caller's
problem to isolate; a call that succeeds returns only clean data.

The BAML ``Nvidia`` client is itself a fallback chain (Gemini -> gpt-oss ->
Ministral), so a single provider timing out is handled below this layer.
"""

from __future__ import annotations

from app.models import ArticleKind, Category
from baml_client.sync_client import b
from baml_client.types import (
    ArticleInput,
    ExistingArticle,
    TagInput,
    TagOption,
)
from pipeline_new.text import clean_summary
from pipeline_new.types import PipelineArticle
from pipeline_new.util import log

# Enough of the body for the model to judge relevance / spot a duplicate; the
# full text would bloat these prompts for no gain.
SNIPPET_CAP = 200


def _to_input(a: PipelineArticle) -> ArticleInput:
    return ArticleInput(
        url=a.url,
        title=a.title,
        source=a.source,
        snippet=a.content[:SNIPPET_CAP] if a.content else None,
        trust=a.trust_tag,
    )


def _enum_value(raw) -> str:
    """The ``.value`` of a BAML enum member, or the raw string — BAML has
    returned either across regenerations, so tolerate both."""
    return str(getattr(raw, "value", raw))


def _to_categories(raw_list) -> list[Category]:
    out: list[Category] = []
    for c in raw_list or []:
        try:
            out.append(Category(_enum_value(c).lower()))
        except ValueError:
            log(f"  Dropped unknown category {_enum_value(c)!r}")
    return out


def _to_kind(raw) -> ArticleKind | None:
    try:
        return ArticleKind(_enum_value(raw).lower())
    except ValueError:
        log(f"  Dropped unknown kind {_enum_value(raw)!r}")
        return None


# ─── Score ───────────────────────────────────────────────────────────────────


def score_batch(articles: list[PipelineArticle]) -> dict[str, int]:
    """URL -> 1-100 relevance score for one batch. Raises on failure so the
    caller can decide the batch's fate; a URL the model omits simply won't be in
    the map and is treated as a reject upstream."""
    result = b.ScoreArticles([_to_input(a) for a in articles])
    return {r.url: r.score for r in result}


# ─── Summary / categories / kind ─────────────────────────────────────────────


def summarize(article: PipelineArticle, content_cap: int) -> tuple[str, list[Category], ArticleKind | None]:
    """Summary + categories + kind for one article that has full content.

    The summary is sanitized and gated (``""`` if the model produced garbage);
    categories and kind drop anything off-schema. One article per call keeps a
    failure to a single item and avoids cross-article blending.
    """
    result = b.SummarizeAndCategorize(article.title, article.content[:content_cap])
    summary = clean_summary(result.summary)
    return summary, _to_categories(result.categories), _to_kind(result.kind)


def categorize_title(article: PipelineArticle) -> list[Category]:
    """Categories from the title alone — the fallback when an article has no
    usable content to summarize."""
    return _to_categories(b.CategorizeOnly(article.title).categories)


# ─── Tags ────────────────────────────────────────────────────────────────────


def assign_tags_batch(
    articles: list[PipelineArticle], vocabulary: dict[str, str]
) -> dict[int, list[str]]:
    """article id -> assigned slugs for one batch. Slugs are echoed back with the
    id, so results match by id, not position. Off-vocabulary slugs are dropped
    here; capping/writing is the caller's job."""
    options = [
        TagOption(slug=slug, description=desc or None)
        for slug, desc in sorted(vocabulary.items())
    ]
    inputs = [
        TagInput(articleId=a.id, title=a.title, summary=a.summary or None)
        for a in articles
        if a.id is not None
    ]
    assignments = b.AssignTags(inputs, options)
    valid = set(vocabulary)
    return {
        a.articleId: [s for s in a.tags if s in valid] for a in assignments
    }


# ─── Semantic dedup ──────────────────────────────────────────────────────────


def semantic_dedup(
    articles: list[PipelineArticle],
    existing: list[tuple[str, str, str]],
) -> set[str]:
    """URLs among ``articles`` that duplicate an already-stored story.

    ``existing`` is ``(url, title, source)`` for the shortlisted recent rows.
    Returns an empty set on any failure — a dedup miss is a tolerable dupe, a
    crash here is not.
    """
    existing_inputs = [
        ExistingArticle(url=u, title=t, source=s) for u, t, s in existing
    ]
    try:
        matches = b.SemanticDedup([_to_input(a) for a in articles], existing_inputs)
    except Exception as e:
        log(f"  Dedup failed, keeping all: {e}")
        return set()
    for m in matches:
        log(f"  Duplicate: {m.url} matches {m.existingUrl}")
    return {m.url for m in matches}
