"""The shared potion-base-8M embedding model.

One process-wide instance, loaded lazily on first use: the keep/drop pre-filter
and the article embed step both encode with it, and it must be the same model in
both places — keep_drop's weights were distilled against these vectors.
"""

from __future__ import annotations

from model2vec import StaticModel

MODEL_NAME = "minishlab/potion-base-8M"

_model: StaticModel | None = None


def get_model() -> StaticModel:
    global _model
    if _model is None:
        _model = StaticModel.from_pretrained(MODEL_NAME)
    return _model


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Encode many texts in one call -> one vector per text, in order."""
    if not texts:
        return []
    return [v.tolist() for v in get_model().encode(texts)]
