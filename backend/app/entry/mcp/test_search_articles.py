"""`search_articles` and `list_tags`: what they take, and what they leave out."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from sqlmodel import Session, col, delete

from app.core.db.factories import (
    create_random_article,
    create_random_tag,
    random_lower_string,
    tag_article,
)
from app.core.db.tag import ArticleTag
from app.entry.mcp.list_tags import list_tags
from app.entry.mcp.search_articles import search_articles


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

    found = search_articles(word)[0]

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
        assert {old.url, new.url} <= {row["url"] for row in search_articles(word)}
        for found in (
            search_articles(word, since="2026-06-01"),
            search_articles(word, kind="repo"),
            search_articles(word, tags=[tag.slug]),
        ):
            urls = [row["url"] for row in found]
            assert urls[0] == new.url
            assert old.url not in urls
        assert len(search_articles(word, limit=1)) == 1
        assert search_articles(word, tags=[tag.slug])[0]["tags"] == [tag.slug]

        counts = {row["slug"]: row["count"] for row in list_tags()}
        assert counts[tag.slug] == 1
    finally:
        db.exec(delete(ArticleTag).where(col(ArticleTag.tag_id) == tag.id))
        db.delete(tag)
        db.commit()


def test_search_names_the_bad_argument() -> None:
    with pytest.raises(ToolError, match="since must be an ISO date"):
        search_articles("anything", since="last week")
    with pytest.raises(ToolError, match="Unknown tag slugs: no-such-tag"):
        search_articles("anything", tags=["no-such-tag"])
    with pytest.raises(ToolError, match="Unknown publisher slug: No Such"):
        search_articles("anything", publisher="No Such")


def test_kind_and_limit_are_constrained_in_the_schema() -> None:
    params = Tool.from_function(search_articles).parameters["properties"]
    assert all(k in str(params["kind"]) for k in ("post", "repo", "paper", "model"))
    assert params["limit"]["maximum"] == 100
    assert params["limit"]["minimum"] == 1


def test_sort_and_an_empty_q_browse_by_score_or_date(
    db: Session, made: dict[str, list[int]]
) -> None:
    word = random_lower_string()
    older_better = create_random_article(
        db,
        title=f"{word} one",
        score=90,
        published_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    newer_worse = create_random_article(
        db,
        title=f"{word} two",
        score=10,
        published_at=datetime(2030, 1, 2, tzinfo=UTC),
    )
    for article in (older_better, newer_worse):
        assert article.id is not None
        made["articles"].append(article.id)
        made["publishers"].append(article.publisher_id)

    def urls(found: list[dict[str, object]]) -> list[object]:
        return [row["url"] for row in found]

    since = "2029-12-31"
    assert urls(search_articles(since=since)) == [older_better.url, newer_worse.url]
    assert urls(search_articles(since=since, sort="recent")) == [
        newer_worse.url,
        older_better.url,
    ]
    by_date = urls(search_articles(word, since=since, sort="recent"))
    assert by_date[:2] == [newer_worse.url, older_better.url]
    by_score = urls(search_articles(word, since=since, sort="score"))
    assert by_score[:2] == [older_better.url, newer_worse.url]
