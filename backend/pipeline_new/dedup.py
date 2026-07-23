"""Embedding shortlist that keeps the dedup LLM prompt small.

Instead of asking the model to compare every new article against the whole
14-day window, an embedding cosine-distance filter first picks the handful of
recent articles each new one might actually duplicate. The pure selection core
is separated from the embedding I/O so it can be tested with synthetic vectors.
"""

from __future__ import annotations

import numpy as np

from pipeline_new.config import dedup_dist_threshold, dedup_topk
from pipeline_new.db import RecentArticle
from pipeline_new.embedding import embed_batch, embed_text
from pipeline_new.types import PipelineArticle


def _cosine_dist(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)
    return 1 - (a_norm @ b_norm.T)


def select_candidates(
    new_vecs: np.ndarray, recent_vecs: np.ndarray, threshold: float, topk: int
) -> set[int]:
    """Recent-vector indices within ``threshold`` cosine distance of any new
    vector, each new one capped to its ``topk`` closest. Pure numpy."""
    if new_vecs.size == 0 or recent_vecs.size == 0:
        return set()
    dist = _cosine_dist(new_vecs, recent_vecs)
    picked: set[int] = set()
    for row in dist:
        within = np.where(row <= threshold)[0]
        if within.size == 0:
            continue
        if within.size > topk:
            within = within[np.argsort(row[within])[:topk]]
        picked.update(within.tolist())
    return picked


def shortlist(
    articles: list[PipelineArticle], recent: list[RecentArticle]
) -> list[tuple[str, str, str]]:
    """The ``(url, title, source)`` recent rows worth sending to the dedup LLM.

    Recent rows without a stored embedding cannot be shortlisted and are skipped
    (the window is expected to be fully embedded).
    """
    # e[3] is a pgvector array; bool() on an array of length > 1 raises, so this
    # must be an explicit "is not None".
    embedded = [r for r in recent if r[3] is not None]
    if not embedded or not articles:
        return []

    new_vecs = np.array(
        embed_batch([embed_text(a.title, a.content) for a in articles]),
        dtype=np.float32,
    )
    recent_vecs = np.array([r[3] for r in embedded], dtype=np.float32)

    picked = select_candidates(
        new_vecs, recent_vecs, dedup_dist_threshold(), dedup_topk()
    )
    return [(str(embedded[i][0]), embedded[i][1], embedded[i][2]) for i in sorted(picked)]
