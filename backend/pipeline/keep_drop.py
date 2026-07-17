"""Tiny keep/drop classifier — a logistic regression distilled from gpt-oss.

Scores an article's `potion-base-8M` embedding into P(keep). Pure numpy: the
model is just a 256-d weight vector + bias exported from the trained
scikit-learn model (see the (now-removed) classifier/ project), so the backend
needs no scikit-learn at runtime.

Used as a cheap cascade PRE-FILTER before the expensive gpt-oss scoring call:
auto-drop only what the classifier is very confident is junk, send everything
else on to gpt-oss for the real 1-100 score. gpt-oss stays the scoring
authority; this only trims obvious noise to cut LLM calls and timeouts.

The embedding text must match training exactly: `title\n\nsummary-or-snippet`,
the same string the embed step builds. Embed with the pipeline's shared
potion-base-8M model, then call `keep_proba(vec)`.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np

_MODEL_PATH = Path(__file__).parent / "keep_drop_model.npz"

# Auto-drop cutoff for the pre-filter. Deliberately low (high recall): only the
# most obvious junk is dropped without asking gpt-oss. The CV sweep put recall
# ~0.99 at 0.3; 0.15 is well inside that safety margin. Set the env var to 0 to
# disable the pre-filter entirely (nothing scores below 0).
DROP_BELOW = float(os.environ.get("KEEP_DROP_PREFILTER_THRESHOLD", "0.15"))

_coef: np.ndarray | None = None
_intercept: float = 0.0
_threshold: float = 0.5


def _load() -> None:
    global _coef, _intercept, _threshold
    if _coef is None:
        d = np.load(_MODEL_PATH)
        _coef = d["coef"].astype("float32")
        _intercept = float(d["intercept"])
        _threshold = float(d["proba_threshold"])


def to_embedding_text(title: str, text: str | None) -> str:
    """One string per article, identical to the embed step / training."""
    title = (title or "").strip()
    text = (text or "").strip()
    return f"{title}\n\n{text}" if text else title


def keep_proba(vec: np.ndarray) -> float:
    """P(keep) for a single 256-d embedding vector."""
    _load()
    z = float(np.dot(vec, _coef)) + _intercept
    return 1.0 / (1.0 + math.exp(-z))


def default_threshold() -> float:
    _load()
    return _threshold
