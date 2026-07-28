"""Pick CATEGORY_GATE_THRESHOLD from data instead of guessing.

The static gate (pipeline.steps.categorize.prefilter_categories) drops any
article whose best cosine similarity to a category prototype falls below a
floor. Set that floor too high and it silently deletes articles the LLM matcher
would have accepted — and nothing downstream can tell that it happened, because
a dropped article leaves no trace beyond a ScoredUrl row.

So the gate ships disabled, and this script is how it gets turned on. Run it
against a restored dump:

    cd backend && uv run python -m scripts.calibrate_category_gate

It scores every article already in the DB against the seeded category
prototypes and prints, for a sweep of candidate floors, what fraction of them
would survive. Read it as a recall curve: the articles in the DB are ones the
old pipeline judged worth keeping, so a floor that drops many of them is a floor
that would have cost real articles.

Pick the highest floor that still clears the recall you are willing to accept —
0.98 is the posture the rest of the pipeline takes (see pipeline.keep_drop) —
and set CATEGORY_GATE_THRESHOLD to it.

Needs the potion-base-8M weights, so it must run somewhere with Hugging Face
reachable.
"""

from __future__ import annotations

import numpy as np
from sqlmodel import Session, col, select

from app.core.db import engine
from app.models import Article
from pipeline.categories import load_vocabulary
from pipeline.embedding import get_model
from pipeline.steps.categorize import GATE_CONTENT_CHARS, max_similarity

# Candidate floors to report. Wide on purpose: the useful range depends on the
# embedding model and on how the category descriptions are worded, and both can
# change.
SWEEP = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]

# Recall the rest of the pipeline's cheap gates are tuned to.
TARGET_RECALL = 0.98


def _gate_text(title: str, content: str | None) -> str:
    """Must match pipeline.steps.categorize.to_gate_text exactly, or the numbers
    below describe a gate that is not the one that runs."""
    title = (title or "").strip()
    body = (content or "").strip()[:GATE_CONTENT_CHARS]
    return f"{title}\n\n{body}" if body else title


def main() -> None:
    with Session(engine) as session:
        vocab = load_vocabulary(session)
        rows = session.exec(
            select(Article.title, Article.content).where(
                col(Article.title).is_not(None)
            )
        ).all()

    if not rows:
        raise SystemExit("no articles in the DB — restore a dump first")

    print(f"{len(rows)} articles, {len(vocab.slugs)} categories")
    print(f"categories: {', '.join(vocab.slugs_ordered)}\n")

    model = get_model()
    vecs = np.asarray(
        model.encode([_gate_text(t, c) for t, c in rows]), dtype=np.float32
    )
    sims = max_similarity(vecs, vocab.prototypes)

    print("similarity distribution")
    for pct in (1, 5, 10, 25, 50, 75, 95):
        print(f"  p{pct:<3} {np.percentile(sims, pct):.3f}")

    print("\nfloor   survive   recall")
    recommended: float | None = None
    for floor in SWEEP:
        survive = int((sims >= floor).sum())
        recall = survive / len(sims)
        mark = ""
        if recall >= TARGET_RECALL:
            recommended = floor
            mark = ""
        else:
            mark = "  <- below target"
        print(f"{floor:<7.2f} {survive:<9} {recall:.3f}{mark}")

    if recommended is None:
        print(
            "\nNo floor in the sweep clears the recall target. Leave the gate "
            "disabled — it cannot pay for itself here."
        )
    else:
        print(
            f"\nHighest floor holding recall >= {TARGET_RECALL}: {recommended:.2f}\n"
            f"    export CATEGORY_GATE_THRESHOLD={recommended:.2f}\n"
            "Sanity-check the titles it would drop before trusting it: they "
            "should read as off-beat, not merely unusual."
        )


if __name__ == "__main__":
    main()
