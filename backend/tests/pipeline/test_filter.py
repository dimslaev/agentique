"""The pure core of the dedup embedding shortlist: which recent articles are
close enough to a new article's embedding to be worth an LLM dedup check.
Pinned separately from the embedding I/O so it runs on synthetic vectors with
no model load.
"""

from __future__ import annotations

import numpy as np

from pipeline.steps.filter import _cosine_dist_matrix, _select_candidate_indices


def test_identical_vectors_have_zero_distance():
    v = np.array([[1.0, 0.0, 0.0]])
    dist = _cosine_dist_matrix(v, v)
    assert dist[0][0] == 0


def test_orthogonal_vectors_have_distance_one():
    a = np.array([[1.0, 0.0]])
    b = np.array([[0.0, 1.0]])
    dist = _cosine_dist_matrix(a, b)
    assert dist[0][0] == 1


def test_scale_does_not_affect_cosine_distance():
    a = np.array([[1.0, 0.0]])
    b = np.array([[5.0, 0.0]])
    dist = _cosine_dist_matrix(a, b)
    assert dist[0][0] == 0


def test_candidates_beyond_threshold_are_excluded():
    new_vecs = np.array([[1.0, 0.0]])
    recent_vecs = np.array([[1.0, 0.0], [0.0, 1.0]])
    idx = _select_candidate_indices(new_vecs, recent_vecs, threshold=0.1, topk=5)
    assert idx == {0}


def test_no_candidates_within_threshold_returns_empty_set():
    new_vecs = np.array([[1.0, 0.0]])
    recent_vecs = np.array([[0.0, 1.0]])
    idx = _select_candidate_indices(new_vecs, recent_vecs, threshold=0.1, topk=5)
    assert idx == set()


def test_capped_to_topk_closest():
    new_vecs = np.array([[1.0, 0.0]])
    # Three near-identical vectors, all within a generous threshold.
    recent_vecs = np.array(
        [
            [1.0, 0.001],
            [1.0, 0.002],
            [1.0, 0.003],
        ]
    )
    idx = _select_candidate_indices(new_vecs, recent_vecs, threshold=0.5, topk=2)
    assert len(idx) == 2
    # The two closest (smallest index offset) should win over the farthest.
    assert 2 not in idx


def test_candidates_union_across_multiple_new_articles():
    new_vecs = np.array([[1.0, 0.0], [0.0, 1.0]])
    recent_vecs = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
    idx = _select_candidate_indices(new_vecs, recent_vecs, threshold=0.1, topk=5)
    assert idx == {0, 1}
