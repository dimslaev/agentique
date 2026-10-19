"""Which article wins when two candidates share a URL."""

from __future__ import annotations

from app.features.curation.model import Scored
from app.features.curation.publish import best_per_url


def _article(url: str, source: str = "Hacker News", score: int = 50) -> Scored:
    return {
        "title": "A title",
        "url": url,
        "content": "body",
        "published_date": None,
        "source": source,
        "publisher_id": 1,
        "score": score,
        "score_reason": None,
    }


def test_same_url_from_two_sources_keeps_the_higher_score() -> None:
    """Two sources can surface one URL in a run (an HN post and a feed item for
    the same post); the URL is the identity, so the better score wins."""
    items = [
        _article("dupe", source="Hacker News", score=40),
        _article("dupe", source="Feeds", score=90),
    ]
    best = best_per_url(items)
    assert len(best) == 1
    assert best[0]["score"] == 90
    assert best[0]["source"] == "Feeds"


def test_higher_score_wins_regardless_of_order() -> None:
    items = [_article("dupe", score=90), _article("dupe", score=40)]
    assert best_per_url(items)[0]["score"] == 90


def test_distinct_urls_all_survive() -> None:
    items = [_article("u1", score=80), _article("u2", score=70)]
    assert len(best_per_url(items)) == 2


def test_empty_input() -> None:
    assert best_per_url([]) == []
