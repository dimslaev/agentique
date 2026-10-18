"""The shared potion-base-8M embedding model, the text every caller embeds, and
the distance maths over the vectors.

One process-wide instance, loaded lazily on first use. The embed step and the
curation agent's `similar` and `stories` must encode the same string for the
same article, or an article fails to match its own stored row, so the text is
built here rather than at each call site.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
from model2vec import StaticModel

MODEL_NAME = "minishlab/potion-base-8M"
# How much of an article goes into its embedding. The title carries most of
# the signal; the opening sentence or two sharpens it.
SNIPPET_CAP = 200

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


def cosine_distances(
    a: npt.NDArray[np.float32], b: npt.NDArray[np.float32]
) -> npt.NDArray[np.float32]:
    """Pairwise cosine distance, rows of ``a`` against rows of ``b``. Pure."""
    if a.size == 0 or b.size == 0:
        return np.empty((a.shape[0], b.shape[0]), dtype=np.float32)
    a_norm = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)
    b_norm = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-12)
    return np.asarray(1 - (a_norm @ b_norm.T), dtype=np.float32)


def nearest(distances: npt.NDArray[np.float32], cutoff: float, limit: int) -> list[int]:
    """Indices of the closest rows within ``cutoff``, closest first. Pure."""
    order = np.argsort(distances, kind="stable")
    return [int(i) for i in order if distances[i] <= cutoff][: max(limit, 0)]


def story_groups(
    distances: npt.NDArray[np.float32], pending: list[bool], cutoff: float
) -> list[list[int]]:
    """Group rows that are the same story, with at least one pending row in each.

    ``distances`` is the square matrix over every row. An edge needs a pending
    row at one end or both, so two feed articles never join a group through each
    other and a chain of loosely related stories cannot grow through the feed.
    Returns only groups of two or more, largest first. Pure.
    """
    n = len(pending)
    parent = list(range(n))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        if not pending[i]:
            continue
        for j in range(n):
            if j != i and distances[i, j] <= cutoff:
                parent[root(j)] = root(i)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(root(i), []).append(i)
    found = [g for g in groups.values() if len(g) >= 2 and any(pending[i] for i in g)]
    return sorted(found, key=len, reverse=True)
