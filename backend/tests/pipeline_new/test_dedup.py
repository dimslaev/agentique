"""The pure core of the dedup shortlist — which recent vectors are close enough
to a new article's embedding to be worth an LLM check. Runs on synthetic
vectors, no model load."""

from __future__ import annotations

import numpy as np

from pipeline_new.dedup import _cosine_dist, select_candidates


def test_identical_vectors_zero_distance() -> None:
    v = np.array([[1.0, 0.0, 0.0]])
    assert _cosine_dist(v, v)[0][0] == 0


def test_orthogonal_vectors_distance_one() -> None:
    a = np.array([[1.0, 0.0]])
    b = np.array([[0.0, 1.0]])
    assert _cosine_dist(a, b)[0][0] == 1


def test_selects_near_and_skips_far() -> None:
    new = np.array([[1.0, 0.0]])
    recent = np.array([[1.0, 0.0], [0.0, 1.0]])  # dup, then unrelated
    picked = select_candidates(new, recent, threshold=0.45, topk=5)
    assert picked == {0}


def test_topk_caps_matches() -> None:
    new = np.array([[1.0, 0.0]])
    recent = np.array([[1.0, 0.0], [1.0, 0.01], [1.0, 0.02]])
    picked = select_candidates(new, recent, threshold=0.45, topk=2)
    assert len(picked) == 2


def test_empty_inputs() -> None:
    assert select_candidates(np.empty((0, 2)), np.array([[1.0, 0.0]]), 0.45, 5) == set()
    assert select_candidates(np.array([[1.0, 0.0]]), np.empty((0, 2)), 0.45, 5) == set()
