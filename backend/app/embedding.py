"""The shared potion-base-8M embedding model.

One process-wide instance, loaded lazily on first use. Every vector in
`article.embedding` and every query vector `/articles/search` compares against
one must come from this model — mixing models silently returns nonsense
neighbours rather than failing.

CPU-only and tiny (~30 MB), so the web worker can hold it.
"""

from __future__ import annotations

from model2vec import StaticModel

MODEL_NAME = "minishlab/potion-base-8M"

# How much of an article's text goes into its vector. Matches what the pipeline
# has always embedded, so vectors written today are comparable with the ones
# already in the table.
EMBED_SNIPPET_CHARS = 200

_model: StaticModel | None = None


def get_model() -> StaticModel:  # pragma: no cover
    global _model
    if _model is None:
        _model = StaticModel.from_pretrained(MODEL_NAME)
    return _model


def embed(text: str) -> list[float]:  # pragma: no cover
    import numpy as np

    vec = get_model().encode([text])[0]
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def embedding_text(title: str, text: str | None) -> str:
    """The one string an article is embedded as: title, then a short snippet.

    Identical to what the pipeline's embed step builds, so an article written
    by the agent lands in the same vector space as everything before it.
    """
    title = (title or "").strip()
    snippet = (text or "").strip()[:EMBED_SNIPPET_CHARS]
    return f"{title}\n\n{snippet}" if snippet else title
