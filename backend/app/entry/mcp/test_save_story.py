"""The `save_story` and `close_story` tools: what they report, and a refusal as
a tool error."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.factories import (
    create_random_article,
    create_random_publisher,
    random_lower_string,
)
from app.entry.mcp.close_story import close_story
from app.entry.mcp.save_story import save_story


def _url(db: Session, made: dict[str, list[int]]) -> str:
    publisher = create_random_publisher(db)
    article = create_random_article(db, publisher_id=publisher.id)
    assert publisher.id is not None and article.id is not None
    made["publishers"].append(publisher.id)
    made["articles"].append(article.id)
    return article.url


@pytest.mark.usefixtures("curator")
def test_save_story_tool_reports_what_it_did(
    db: Session, made: dict[str, list[int]]
) -> None:
    slug = f"tool-made-{random_lower_string()[:6]}"
    assert save_story(slug, "Tool made", "It works.", [_url(db, made)]) == (
        f"Created {slug}: added 1, 1 articles in all"
    )
    assert save_story(slug, "Tool made", "It still works.", [_url(db, made)]) == (
        f"Updated {slug}: added 1, 2 articles in all"
    )
    assert close_story(slug) == f"Closed {slug}"


@pytest.mark.usefixtures("curator")
def test_save_story_refuses_an_unknown_url_as_a_tool_error() -> None:
    slug = f"tool-refused-{random_lower_string()[:6]}"
    with pytest.raises(ToolError, match="Not a published article"):
        save_story(
            slug, "Tool refused", "It fails.", ["https://never-published.example/post"]
        )


@pytest.mark.usefixtures("curator")
def test_close_story_refuses_an_unknown_slug_as_a_tool_error() -> None:
    with pytest.raises(ToolError, match="No story"):
        close_story(f"no-such-story-{random_lower_string()[:6]}")
