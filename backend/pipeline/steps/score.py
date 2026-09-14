"""Step 3: rate what survived filtering, keep what clears the bar.

A cascade: the tiny distilled keep/drop classifier throws out obvious junk for
free, then the LLM scores the rest 1-100. The LLM stays the scoring authority —
the classifier only trims noise so we make fewer, cheaper LLM calls.
"""

from __future__ import annotations

from sqlmodel import Session

from app.catalog.models import PublisherKind, TrustLevel
from app.platform.logging import log, short_error, wait_ms
from baml_client.sync_client import b
from pipeline import keep_drop
from pipeline.embedding import get_model
from pipeline.llm_text import sanitize_llm_text
from pipeline.models import RejectStage
from pipeline.rejects import record_reject
from pipeline.steps import to_baml_input
from pipeline.types import Candidate, Scored

# Tied to the rubric in baml_src/score.baml: the median in-scope article sits
# near 55 there, so this admits roughly the top third. Moving one without the
# other either empties the feed or fills it with newsletter filler.
SCORE_THRESHOLD = 65
# Hand-picked individual writers (a high-trust publisher of kind individual)
# clear a lower bar. The feed is meant to carry them over one more vendor
# post, and asking the scorer to favour them does not work: its +3 trust
# nudge drowns in its own run-to-run noise, and a prompt that favours
# individuals lifts every solo landing page with them.
CURATED_INDIVIDUAL_THRESHOLD = 55
SCORE_BATCH = 5
# Pause between scoring batches to stay under the provider's rate limit.
SCORE_BATCH_PAUSE_MS = 1000


def threshold_for(trust: str, kind: str) -> int:
    """The score an article needs to be kept, given its publisher. Pure."""
    if trust == TrustLevel.high and kind == PublisherKind.individual:
        return CURATED_INDIVIDUAL_THRESHOLD
    return SCORE_THRESHOLD


def prefilter_keep_drop(session: Session, articles: list[Candidate]) -> list[Candidate]:
    """Drop obvious junk before the LLM scorer.

    Runs the tiny distilled classifier on title+snippet. Anything it is very
    confident is a drop (P(keep) < threshold) is discarded without an LLM call
    and recorded as a reject so it is not re-fetched. Everything else passes
    through for real scoring.
    """
    threshold = keep_drop.drop_below()
    if not articles or threshold <= 0:
        return articles

    texts = [keep_drop.to_embedding_text(a["title"], a["content"]) for a in articles]
    vecs = get_model().encode(texts)

    survivors: list[Candidate] = []
    dropped = 0
    for a, vec in zip(articles, vecs, strict=True):
        p_keep = keep_drop.keep_proba(vec)
        if p_keep < threshold:
            record_reject(
                session,
                a,
                RejectStage.prefilter,
                detail={"keep_proba": round(p_keep, 3)},
            )
            dropped += 1
        else:
            survivors.append(a)
    if dropped:
        session.commit()

    log(
        f"  Pre-filter dropped {dropped}/{len(articles)} as obvious junk "
        f"(P(keep) < {threshold}); {len(survivors)} to scorer"
    )
    return survivors


def apply_scores(
    articles: list[Candidate],
    score_by_url: dict[str, int],
    reason_by_url: dict[str, str] | None = None,
) -> list[Scored]:
    """Attach each article's score and reason, and sort best-first. Pure: no I/O.

    An article the scorer did not return scores 0 and so falls below the
    threshold — a missing score is treated as a reject, never as a pass.
    """
    reasons = reason_by_url or {}
    scored: list[Scored] = []
    for a in articles:
        score = score_by_url.get(a["url"], 0)
        scored.append({**a, "score": score, "score_reason": reasons.get(a["url"])})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def score_articles(session: Session, articles: list[Candidate]) -> list[Scored]:
    if not articles:
        return []

    batches = (len(articles) + SCORE_BATCH - 1) // SCORE_BATCH
    log(f"  Scoring {len(articles)} articles in batches of {SCORE_BATCH}...")

    score_by_url: dict[str, int] = {}
    reason_by_url: dict[str, str] = {}
    # Only the articles a scoring call actually came back for. A batch whose
    # call failed is left out entirely: apply_scores reads a missing score as 0
    # and the sub-threshold URLs below get recorded as rejects, so scoring the
    # batch anyway would turn a provider outage into a permanent drop.
    judged: list[Candidate] = []
    failed = 0
    last_error: Exception | None = None
    for i in range(0, len(articles), SCORE_BATCH):
        batch = articles[i : i + SCORE_BATCH]
        try:
            result = b.ScoreArticles([to_baml_input(a) for a in batch])
        except Exception as e:
            # One failed batch costs its own five articles, never the source:
            # run.py treats a raise here as the whole source failing, which on
            # 2026-09-03 cost 121 fetched Feeds articles over one bad call.
            # They stay unrecorded, so the next run re-reads them.
            failed += 1
            last_error = e
            log(f"    batch {i // SCORE_BATCH + 1}/{batches} failed: {short_error(e)}")
        else:
            judged.extend(batch)
            score_by_url.update({r.url: r.score for r in result})
            reason_by_url.update({r.url: sanitize_llm_text(r.reason) for r in result})
            log(f"    batch {i // SCORE_BATCH + 1}/{batches} done")
        if i + SCORE_BATCH < len(articles):
            wait_ms(SCORE_BATCH_PAUSE_MS)

    if failed:
        log(
            f"  {failed}/{batches} scoring batches failed — "
            "their articles are held for the next run"
        )
    # Every batch failing is not a bad call, it is the scorer being down. Let it
    # out so the source records the error and the verifier alerts on it; a
    # partial failure is left to the yield-drop check instead.
    if last_error is not None and not judged:
        raise last_error

    scored = apply_scores(judged, score_by_url, reason_by_url)
    kept = [
        s
        for s in scored
        if s["score"] >= threshold_for(s["trust"], s["publisher_kind"])
    ]
    log(
        f"  {len(kept)} articles pass scoring (threshold: {SCORE_THRESHOLD}, "
        f"{CURATED_INDIVIDUAL_THRESHOLD} for curated individuals)"
    )

    # Record only sub-threshold URLs so they are not re-fetched next run. Keepers
    # are deliberately NOT recorded here: a crash between this commit and the
    # insert would otherwise mark them "scored" and drop them forever. Once
    # inserted, the Article row itself makes them known (see filter_known_urls).
    # A score of 0 with no reason is an article the scorer did not return.
    below = [
        s for s in scored if s["score"] < threshold_for(s["trust"], s["publisher_kind"])
    ]
    for s in below:
        record_reject(
            session,
            s,
            RejectStage.below_threshold,
            score=s["score"],
            reason=s["score_reason"],
        )
    if below:
        session.commit()

    return kept
