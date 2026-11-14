"""`search` and `tags`: what they take, and what they leave out."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastmcp.exceptions import ToolError
from sqlmodel import Session, col, delete

from app.core.db.factories import (
    create_random_article,
    create_random_tag,
    random_lower_string,
    tag_article,
)
from app.core.db.tag import ArticleTag
from app.entry.mcp.search import search
from app.entry.mcp.tags import tags


@pytest.fixture(autouse=True)
def _embed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.features.catalog.search.embed", lambda _text: [0.05] * 256)


def test_search_returns_a_link_and_an_excerpt_but_not_the_text(
    db: Session, made: dict[str, list[int]]
) -> None:
    word = random_lower_string()
    filler = " ".join(random_lower_string() for _ in range(200))
    article = create_random_article(
        db,
        title=f"Notes on {word}",
        content=f"{filler} then {word} appears. {filler}",
        published_at=datetime(2026, 10, 5, tzinfo=UTC),
    )
    assert article.id is not None
    made["articles"].append(article.id)
    made["publishers"].append(article.publisher_id)

    # Other articles can follow by meaning. The keyword match is first.
    found = search(word)[0]

    assert set(found) == {
        "id",
        "title",
        "url",
        "publisher",
        "published_at",
        "score",
        "summary",
        "tags",
        "excerpt",
    }
    assert found["url"] == article.url
    assert isinstance(found["excerpt"], str)
    assert word in found["excerpt"]
    assert len(found["excerpt"]) <= 300


def test_search_filters_narrow_the_results(
    db: Session, made: dict[str, list[int]]
) -> None:
    word = random_lower_string()
    old = create_random_article(
        db, title=f"{word} one", published_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    new = create_random_article(
        db,
        title=f"{word} two",
        kind="repo",
        published_at=datetime(2026, 10, 1, tzinfo=UTC),
    )
    for article in (old, new):
        assert article.id is not None
        made["articles"].append(article.id)
        made["publishers"].append(article.publisher_id)
    tag = create_random_tag(db)
    tag_article(db, new, tag)

    try:
        assert {old.url, new.url} <= {row["url"] for row in search(word)}
        for found in (
            search(word, since="2026-06-01"),
            search(word, kind="repo"),
            search(word, tags=[tag.slug]),
        ):
            urls = [row["url"] for row in found]
            assert urls[0] == new.url
            assert old.url not in urls
        assert len(search(word, limit=1)) == 1
        assert search(word, tags=[tag.slug])[0]["tags"] == [tag.slug]

        counts = {row["slug"]: row["count"] for row in tags()}
        assert counts[tag.slug] == 1
    finally:
        db.exec(delete(ArticleTag).where(col(ArticleTag.tag_id) == tag.id))
        db.delete(tag)
        db.commit()


def test_search_names_the_bad_argument() -> None:
    with pytest.raises(ToolError, match="kind must be one of: post, repo, paper"):
        search("anything", kind="video")
    with pytest.raises(ToolError, match="since must be an ISO date"):
        search("anything", since="last week")
    with pytest.raises(ToolError, match="limit must be at least 1"):
        search("anything", limit=0)
