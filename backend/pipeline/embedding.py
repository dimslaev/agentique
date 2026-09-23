"""The shared potion-base-8M embedding model, and the text every caller embeds.

One process-wide instance, loaded lazily on first use. The embed step and the
curation agent's `similar` and `stories` must encode the same string for the
same article, or an article fails to match its own stored row, so the text is
built here rather than at each call site.
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


def to_embedding_text(title: str, text: str | None) -> str:
    """One string per article: title, blank line, then the snippet if there is one."""
    title = (title or "").strip()
    text = (text or "").strip()
    return f"{title}\n\n{text}" if text else title
