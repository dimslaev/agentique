"""The pure core of semantic dedup: which recent article, if any, a new
article is close enough to be a duplicate of. Pinned separately from the
embedding I/O so it runs on synthetic vectors with no model load.
"""

from __future__ import annotations

import numpy as np

from pipeline.steps.filter import _cosine_dist_matrix, _nearest_within


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


def test_duplicate_within_threshold_is_matched():
    new_vecs = np.array([[1.0, 0.0]])
    existing_vecs = np.array([[1.0, 0.0], [0.0, 1.0]])
    assert _nearest_within(new_vecs, existing_vecs, threshold=0.1) == {0: 0}


def test_nothing_within_threshold_matches_nothing():
    new_vecs = np.array([[1.0, 0.0]])
    existing_vecs = np.array([[0.0, 1.0]])
    assert _nearest_within(new_vecs, existing_vecs, threshold=0.1) == {}


def test_closest_existing_wins_when_several_are_within_threshold():
    new_vecs = np.array([[1.0, 0.0]])
    # Index 1 is nearest; all three sit inside a generous threshold.
    existing_vecs = np.array([[1.0, 0.30], [1.0, 0.01], [1.0, 0.20]])
    assert _nearest_within(new_vecs, existing_vecs, threshold=0.5) == {0: 1}


def test_each_new_article_is_judged_independently():
    new_vecs = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
    existing_vecs = np.array([[1.0, 0.0], [0.0, 1.0]])
    # The third is opposite to everything existing, so it survives.
    assert _nearest_within(new_vecs, existing_vecs, threshold=0.1) == {0: 0, 1: 1}


def test_empty_inputs_match_nothing():
    empty = np.empty((0, 2), dtype=np.float32)
    populated = np.array([[1.0, 0.0]])
    assert _nearest_within(empty, populated, threshold=0.9) == {}
    assert _nearest_within(populated, empty, threshold=0.9) == {}


def test_threshold_boundary_is_inclusive():
    a = np.array([[1.0, 0.0]])
    b = np.array([[0.0, 1.0]])
    exact = float(_cosine_dist_matrix(a, b)[0][0])
    assert _nearest_within(a, b, threshold=exact) == {0: 0}
