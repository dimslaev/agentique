"""The `search_articles` tool: find articles by keyword and by meaning."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastmcp.exceptions import ToolError
from pydantic import Field
from sqlmodel import Session, col, select

from app.core.db.engine import engine
from app.core.db.publisher import Publisher
from app.core.db.tag import Tag
from app.features.catalog import service as catalog

# The feed's own sort keys, for a search with no words to rank by.
_FEED_SORT = {
    "relevance": "score-desc",
    "score": "score-desc",
    "recent": "published_at-desc",
}
# How many matches a search reads before re-sorting them by score or date.
_POOL = 100


def search_articles(
    q: str = "",
    tags: list[str] | None = None,
    kind: Literal["post", "repo", "paper", "model"] | None = None,
    since: str | None = None,
    publisher: str | None = None,
    sort: Literal["relevance", "score", "recent"] = "relevance",
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
) -> list[dict[str, object]]:
    """Search agentique's archive of curated AI articles.

    `q` is keywords or a plain question. Keywords match the title, summary,
    full text and tag names; `"quoted phrase"`, `or` and `-exclude` work. The
    meaning of `q` is matched too, so a result may hold none of the words.
    Leave `q` empty to browse by the filters alone, such as the best articles
    since a date.

    Filters narrow the articles before they are ranked:
    - `tags`: tag slugs, matching any of them. Call `list_tags` first for the slugs.
    - `kind`: one kind of article.
    - `since`: an ISO date, such as `2026-10-01`. Omit for all time.
    - `publisher`: a publisher slug, such as `anthropic`, as a result's
      `publisher.slug` gives it. Not the display name.

    `sort`: `relevance` (best match first; with an empty `q`, same as
    `score`), `score` (most useful first) or `recent` (newest first). With a
    `q`, `score` and `recent` reorder the 100 best matches.

    Each result has `id`, `title`, `url`, `publisher`, `published_at`, `score`
    (1-100, how useful it is to someone building with AI), `summary`, `tags`
    and `excerpt`, about 300 characters of the text around the keywords (null
    with an empty `q`). The full text is not returned: follow `url` to read
    the article.
    """
    try:
        since_at = datetime.fromisoformat(since) if since else None
    except ValueError:
        raise ToolError("since must be an ISO date, such as 2026-10-01")

    with Session(engine) as session:
        _reject_unknown(session, tags, publisher)
        kinds: list[str] | None = [kind] if kind else None
        if not q.strip():
            found = catalog.list_articles(
                session,
                limit=limit,
                sort=_FEED_SORT[sort],
                tags=tags,
                kinds=kinds,
                since=since_at,
                publisher=publisher,
            ).data
        else:
            found = catalog.search(
                session,
                q,
                limit if sort == "relevance" else _POOL,
                tags=tags,
                kinds=kinds,
                since=since_at,
                publisher=publisher,
            ).data
            if sort != "relevance":
                key = "score" if sort == "score" else "published_at"
                found = sorted(found, key=lambda a: getattr(a, key), reverse=True)
                found = found[:limit]
    return [
        {
            "id": article.id,
            "title": article.title,
            "url": article.url,
            "publisher": {
                "slug": article.publisher.slug,
                "name": article.publisher.name,
            },
            "published_at": article.published_at,
            "score": article.score,
            "summary": article.summary,
            "tags": [tag.slug for tag in article.tags],
            "excerpt": article.excerpt,
        }
        for article in found
    ]


def _reject_unknown(
    session: Session, tags: list[str] | None, publisher: str | None
) -> None:
    """Name a slug that matches nothing, rather than return no results."""
    if tags:
        known = set(session.exec(select(Tag.slug).where(col(Tag.slug).in_(tags))))
        unknown = sorted(set(tags) - known)
        if unknown:
            raise ToolError(
                f"Unknown tag slugs: {', '.join(unknown)}. Call `list_tags` for the list."
            )
    if (
        publisher is not None
        and not session.exec(
            select(Publisher.id).where(Publisher.slug == publisher)
        ).first()
    ):
        raise ToolError(
            f"Unknown publisher slug: {publisher}. Use a lowercase slug, such as "
            "`anthropic`, from a result's `publisher.slug` or the `publisher` view."
        )
