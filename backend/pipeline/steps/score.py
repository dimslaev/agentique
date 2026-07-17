"""Step 3: rate what survived filtering, keep what clears the bar.

A cascade: the tiny distilled keep/drop classifier throws out obvious junk for
free, then the LLM scores the rest 1-100. The LLM stays the scoring authority —
the classifier only trims noise so we make fewer, cheaper LLM calls.
"""

from __future__ import annotations

from sqlmodel import Session

from app.models_agentique import ScoredUrl
from baml_client.sync_client import b
from pipeline import keep_drop
from pipeline.embedding import get_model
from pipeline.heuristics import SCORE_THRESHOLD
from pipeline.steps import to_baml_input
from pipeline.types import FetchedArticle
from pipeline.utils import log, wait_ms

SCORE_BATCH = 5
# Pause between scoring batches to stay under the provider's rate limit.
SCORE_BATCH_PAUSE_MS = 1000


def prefilter_keep_drop(
    session: Session, articles: list[FetchedArticle]
) -> list[FetchedArticle]:
    """Drop obvious junk before the LLM scorer.

    Runs the tiny distilled classifier on title+snippet. Anything it is very
    confident is a drop (P(keep) < keep_drop.DROP_BELOW) is discarded without an
    LLM call and recorded in ScoredUrl so it is not re-fetched. Everything else
    passes through for real scoring.
    """
    if not articles or keep_drop.DROP_BELOW <= 0:
        return articles

    texts = [
        keep_drop.to_embedding_text(a["title"], a.get("content")) for a in articles
    ]
    vecs = get_model().encode(texts)

    survivors: list[FetchedArticle] = []
    dropped = 0
    for a, vec in zip(articles, vecs, strict=True):
        if keep_drop.keep_proba(vec) < keep_drop.DROP_BELOW:
            session.merge(ScoredUrl(url=a["url"]))
            dropped += 1
        else:
            survivors.append(a)
    if dropped:
        session.commit()

    log(
        f"  Pre-filter dropped {dropped}/{len(articles)} as obvious junk "
        f"(P(keep) < {keep_drop.DROP_BELOW}); {len(survivors)} to scorer"
    )
    return survivors


def apply_scores(
    articles: list[FetchedArticle], score_by_url: dict[str, int]
) -> list[FetchedArticle]:
    """Attach each article's score and sort best-first. Pure: no I/O.

    An article the scorer did not return scores 0 and so falls below the
    threshold — a missing score is treated as a reject, never as a pass.
    """
    scored: list[FetchedArticle] = []
    for a in articles:
        score = score_by_url.get(a["url"], 0)
        # TODO(new-schema): hard-coded per-source score bonus. Once publishers
        # carry a boost/weight field this should read from the Publisher row
        # (a["trust"] is already available) instead of matching a name string.
        if a["source"] == "Ben's Bites":
            score = min(score + 10, 100)
        scored.append({**a, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def score_articles(
    session: Session, articles: list[FetchedArticle]
) -> list[FetchedArticle]:
    if not articles:
        return []

    batches = (len(articles) + SCORE_BATCH - 1) // SCORE_BATCH
    log(f"  Scoring {len(articles)} articles in batches of {SCORE_BATCH}...")

    score_by_url: dict[str, int] = {}
    for i in range(0, len(articles), SCORE_BATCH):
        batch = articles[i : i + SCORE_BATCH]
        result = b.ScoreArticles([to_baml_input(a) for a in batch])
        score_by_url.update({r.url: r.score for r in result})
        log(f"    batch {i // SCORE_BATCH + 1}/{batches} done")
        wait_ms(SCORE_BATCH_PAUSE_MS)

    scored = apply_scores(articles, score_by_url)
    kept = [s for s in scored if s["score"] >= SCORE_THRESHOLD]
    log(f"  {len(kept)} articles pass scoring (threshold: {SCORE_THRESHOLD})")

    # Record only sub-threshold URLs so they are not re-fetched next run. Keepers
    # are deliberately NOT recorded here: a crash between this commit and the
    # insert would otherwise mark them "scored" and drop them forever. Once
    # inserted, the Article row itself makes them known (see filter_known_urls).
    below = [s for s in scored if s["score"] < SCORE_THRESHOLD]
    for s in below:
        session.merge(ScoredUrl(url=s["url"]))
    if below:
        session.commit()

    return kept
