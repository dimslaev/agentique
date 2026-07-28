"""Step 3: decide what the site is about, and drop everything else.

This replaces the old score-1-to-100 step. Scoring answered "how good is this?",
which is a global axis — an article could score 85 and still belong to no lane
on the homepage, and it got stored anyway. This step answers the local question
instead: does this article match one of our categories? Nothing that matches
none is stored, so the category list stops being a view over the corpus and
becomes the filter that defines it.

Three gates, cheapest first, each only seeing what the previous could not rule
out:

  0. keep/drop classifier  - is this AI developer news at all?     (numpy)
  1. prototype floor       - is it near any category we cover?     (numpy)
  2. MatchCategories       - which categories, specifically?       (LLM)

Gates 0 and 1 are deliberately high-recall: they exist to cut LLM calls, not to
make editorial decisions. Gate 2 is the authority, and an empty answer from it
is a normal outcome.
"""

from __future__ import annotations

import numpy as np
from sqlmodel import Session

from app.models import ScoredUrl
from baml_client.sync_client import b
from baml_client.types import CategoryOption
from pipeline import keep_drop
from pipeline.categories import Vocabulary, validate_categories
from pipeline.config import category_gate_threshold
from pipeline.embedding import get_model
from pipeline.steps import to_baml_input
from pipeline.types import FetchedArticle
from pipeline.utils import log, wait_ms

# Articles per MatchCategories call. Larger than the old scoring batch of 5: the
# per-article payload is just title + snippet, and the vocabulary — the bulk of
# the prompt — is sent once per batch regardless of size.
MATCH_BATCH = 8
# Pause between batches to stay under the provider's rate limit.
MATCH_BATCH_PAUSE_MS = 1000

# How much of an article's body the static gate sees. potion-base-8M averages
# token vectors, so feeding it the full text drowns the subject in boilerplate;
# the opening of an article is where it says what it is about.
GATE_CONTENT_CHARS = 500


def _record_dropped(session: Session, articles: list[FetchedArticle]) -> None:
    """Remember a rejected URL so the next run does not re-fetch and re-judge it.

    Same ScoredUrl table the scorer used — the column name outlived the score.
    """
    for a in articles:
        session.merge(ScoredUrl(url=a["url"]))
    if articles:
        session.commit()


# ─── Gate 0: keep/drop classifier ────────────────────────────────────────────


def prefilter_keep_drop(
    session: Session, articles: list[FetchedArticle]
) -> list[FetchedArticle]:
    """Drop obvious non-AI junk before anything expensive.

    The tiny distilled classifier over title+snippet. Anything it is very
    confident is a drop (P(keep) < threshold) is discarded and recorded, no LLM
    call. Everything else passes through. Unchanged from the scoring pipeline —
    it answers "is this AI developer news", which is still the first question.
    """
    threshold = keep_drop.drop_below()
    if not articles or threshold <= 0:
        return articles

    texts = [
        keep_drop.to_embedding_text(a["title"], a.get("content")) for a in articles
    ]
    vecs = get_model().encode(texts)

    survivors: list[FetchedArticle] = []
    dropped: list[FetchedArticle] = []
    for a, vec in zip(articles, vecs, strict=True):
        if keep_drop.keep_proba(vec) < threshold:
            dropped.append(a)
        else:
            survivors.append(a)
    _record_dropped(session, dropped)

    log(
        f"  Gate 0 dropped {len(dropped)}/{len(articles)} as obvious junk "
        f"(P(keep) < {threshold}); {len(survivors)} remain"
    )
    return survivors


# ─── Gate 1: static prototype floor ──────────────────────────────────────────


def to_gate_text(article: FetchedArticle) -> str:
    """The string the static category gate embeds for one article."""
    title = (article.get("title") or "").strip()
    content = (article.get("content") or "").strip()[:GATE_CONTENT_CHARS]
    return f"{title}\n\n{content}" if content else title


def max_similarity(vecs: np.ndarray, prototypes: np.ndarray) -> np.ndarray:
    """Best cosine similarity to any category prototype, per article. Pure numpy.

    ``prototypes`` arrives L2-normalised from the vocabulary loader; article
    vectors are normalised here. Kept separate from the DB and the model so it
    can be tested with synthetic vectors.
    """
    if vecs.size == 0 or prototypes.size == 0:
        return np.zeros(len(vecs), dtype=np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    normalized = vecs / np.where(norms == 0, 1.0, norms)
    return (normalized @ prototypes.T).max(axis=1)


def prefilter_categories(
    session: Session, articles: list[FetchedArticle], vocab: Vocabulary
) -> list[FetchedArticle]:
    """Drop articles that are not close to any category we cover.

    Cosine similarity against the per-category prototype vectors, on the same
    potion-base-8M model gate 0 uses. A static model is a blunt instrument for
    this, so the floor is set for recall, not precision — it is here to stop
    us paying for an LLM call on an article about, say, chip export policy that
    gate 0 was happy to keep as "AI news". Set the env var to 0 to disable.
    """
    threshold = category_gate_threshold()
    if not articles or threshold <= 0:
        return articles

    vecs = np.asarray(
        get_model().encode([to_gate_text(a) for a in articles]), dtype=np.float32
    )
    sims = max_similarity(vecs, vocab.prototypes)

    survivors = [a for a, s in zip(articles, sims, strict=True) if s >= threshold]
    dropped = [a for a, s in zip(articles, sims, strict=True) if s < threshold]
    for a, s in zip(articles, sims, strict=True):
        if s < threshold:
            log(f"  Gate 1 dropped (sim {s:.3f}): {a['title'][:70]}")
    _record_dropped(session, dropped)

    log(
        f"  Gate 1 dropped {len(dropped)}/{len(articles)} as off-topic "
        f"(max prototype sim < {threshold}); {len(survivors)} to the matcher"
    )
    return survivors


# ─── Gate 2: the LLM matcher ─────────────────────────────────────────────────


def category_options(vocab: Vocabulary) -> list[CategoryOption]:
    """The vocabulary as the prompt sees it, in homepage lane order.

    The display name comes from the DB, not from prettifying the slug — the
    prompt shows "Tool Use & MCP" next to `tool-use-mcp`, and a model that
    echoes the name instead of the slug is caught by `validate_categories`.
    """
    return [
        CategoryOption(
            slug=slug,
            name=vocab.slug_to_name[slug],
            description=vocab.slug_to_description[slug],
        )
        for slug in vocab.slugs_ordered
    ]


def apply_matches(
    articles: list[FetchedArticle],
    categories_by_url: dict[str, list[str]],
    valid: frozenset[str],
) -> list[FetchedArticle]:
    """Stamp each article with its validated categories and keep the matches.
    Pure: no I/O.

    An article the matcher did not return at all gets no categories and is
    therefore dropped — a missing answer is a reject, never a pass. This mirrors
    how the old scorer treated a missing score as 0.
    """
    matched: list[FetchedArticle] = []
    for a in articles:
        slugs = validate_categories(categories_by_url.get(a["url"], []), valid)
        if slugs:
            matched.append({**a, "categories": slugs})
    return matched


def match_categories(
    session: Session, articles: list[FetchedArticle], vocab: Vocabulary
) -> list[FetchedArticle]:
    """Ask which categories each article belongs to; keep the ones that match at
    least one.

    Batched, with the vocabulary sent once per batch. A failed batch drops that
    batch's articles rather than the run — and because they are never recorded
    in ScoredUrl on failure, the next run retries them. Deliberate: a provider
    timeout must not silently blacklist good articles.
    """
    if not articles:
        return []

    log(f"  Matching {len(articles)} articles against {len(vocab.slugs)} categories...")
    options = category_options(vocab)

    categories_by_url: dict[str, list[str]] = {}
    failed_urls: set[str] = set()
    for i in range(0, len(articles), MATCH_BATCH):
        batch = articles[i : i + MATCH_BATCH]
        try:
            matches = b.MatchCategories([to_baml_input(a) for a in batch], options)
        except Exception as e:
            log(
                f"  Match failed for batch {i // MATCH_BATCH + 1}, retrying next run: {e}"
            )
            failed_urls.update(a["url"] for a in batch)
            continue
        categories_by_url.update({m.url: list(m.categories) for m in matches})
        if i + MATCH_BATCH < len(articles):
            wait_ms(MATCH_BATCH_PAUSE_MS)

    matched = apply_matches(articles, categories_by_url, vocab.slugs)
    matched_urls = {a["url"] for a in matched}

    # Judged and rejected -> remember it. Never judged (batch failed) -> leave it
    # alone so it comes back.
    _record_dropped(
        session,
        [
            a
            for a in articles
            if a["url"] not in matched_urls and a["url"] not in failed_urls
        ],
    )

    for a in matched:
        log(f"  Matched [{', '.join(a['categories'])}]: {a['title'][:70]}")
    log(
        f"  Gate 2 matched {len(matched)}/{len(articles)} "
        f"({len(failed_urls)} deferred by errors)"
    )
    return matched
