"""The shared potion-base-8M embedding model + the keep/drop pre-filter.

One process-wide model, loaded lazily on first use. The keep/drop classifier and
the article embed step must encode with the *same* model and the *same* text
recipe — the classifier's weights were distilled against these exact vectors.

The keep/drop classifier is a logistic regression (a 256-d weight vector + bias,
exported to ``keep_drop_model.npz``) distilled from the LLM scorer. It runs as a
cheap cascade before the expensive scoring call: auto-drop only what it is very
confident is junk, send everything else on to the LLM. The LLM stays the scoring
authority — this only trims obvious noise to cut LLM calls and timeouts.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from model2vec import StaticModel

from pipeline_new.config import keep_drop_threshold

MODEL_NAME = "minishlab/potion-base-8M"
_MODEL_PATH = Path(__file__).parent / "keep_drop_model.npz"

_model: StaticModel | None = None
_coef: np.ndarray | None = None
_intercept: float = 0.0


def get_model() -> StaticModel:
    global _model
    if _model is None:
        _model = StaticModel.from_pretrained(MODEL_NAME)
    return _model


def embed_text(title: str, body: str | None) -> str:
    """The one string per article the model encodes — identical between the
    pre-filter and the final embed, and to the classifier's training text."""
    title = (title or "").strip()
    body = (body or "").strip()
    return f"{title}\n\n{body}" if body else title


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Encode many texts in one call -> one vector per text, in order."""
    if not texts:
        return []
    return [v.tolist() for v in get_model().encode(texts)]


def _load_classifier() -> None:
    global _coef, _intercept
    if _coef is None:
        d = np.load(_MODEL_PATH)
        _coef = d["coef"].astype("float32")
        _intercept = float(d["intercept"])


def keep_proba(vec: np.ndarray) -> float:
    """P(keep) for a single 256-d embedding vector."""
    _load_classifier()
    z = float(np.dot(vec, _coef)) + _intercept
    return 1.0 / (1.0 + math.exp(-z))


def drop_threshold() -> float:
    """P(keep) below which the pre-filter auto-drops; 0 disables it."""
    return keep_drop_threshold()
