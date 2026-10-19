"""The distance maths `similar`, `stories`, the newsletter and the stories rail
all group by. Pure: synthetic vectors, no model load."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from app.core import embedding


def _vecs(*rows: list[float]) -> npt.NDArray[np.float32]:
    return np.array(rows, dtype=np.float32)


def test_cosine_distance_is_zero_for_the_same_direction() -> None:
    d = embedding.cosine_distances(_vecs([1, 0]), _vecs([2, 0], [0, 1], [-1, 0]))
    assert np.allclose(d, [[0, 1, 2]])


def test_cosine_distance_survives_a_zero_vector() -> None:
    d = embedding.cosine_distances(_vecs([0, 0]), _vecs([1, 0]))
    assert np.isfinite(d).all()


def test_nearest_is_closest_first_within_the_cutoff() -> None:
    distances = np.array([0.40, 0.10, 0.50, 0.25], dtype=np.float32)
    assert embedding.nearest(distances, cutoff=0.45, limit=8) == [1, 3, 0]
    assert embedding.nearest(distances, cutoff=0.45, limit=2) == [1, 3]


def test_story_groups_join_pending_rows_with_each_other_and_the_feed() -> None:
    # 0, 1 pending and the same story; 2 a feed article on it; 3 a pending
    # candidate on its own; 4 a feed article on nothing queued.
    vecs = _vecs([1, 0, 0], [0.98, 0.1, 0], [0.97, 0.12, 0], [0, 1, 0], [0, 0, 1])
    pending = [True, True, False, True, False]

    groups = embedding.story_groups(
        embedding.cosine_distances(vecs, vecs), pending, 0.30
    )

    assert [sorted(g) for g in groups] == [[0, 1, 2]]


def test_feed_articles_do_not_chain_a_group_through_each_other() -> None:
    # Pending 0 is close to article 1; article 2 is close to article 1 but not
    # to 0. Without a pending end on every edge, 2 would ride in through 1.
    distances = np.array(
        [
            [0.0, 0.2, 0.6],
            [0.2, 0.0, 0.2],
            [0.6, 0.2, 0.0],
        ]
    )
    groups = embedding.story_groups(distances, [True, False, False], 0.30)
    assert [sorted(g) for g in groups] == [[0, 1]]


def test_a_group_of_feed_articles_alone_is_not_a_story() -> None:
    distances = np.array([[0.0, 0.1], [0.1, 0.0]], dtype=np.float32)
    assert embedding.story_groups(distances, [False, False], 0.30) == []
