"""The `search` tool: find articles by keyword and by meaning."""

from __future__ import annotations

from datetime import datetime

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.article import ArticleKind
from app.core.db.engine import engine
from app.features.catalog import service as catalog


def search(
    q: str,
    tags: list[str] | None = None,
    kind: str | None = None,
    since: str | None = None,
    publisher: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    """Search agentique's archive of curated AI articles, best match first.

    `q` is keywords or a plain question. Keywords match the title, summary,
    full text and tag names; `"quoted phrase"`, `or` and `-exclude` work. The
    meaning of `q` is matched too, so a result may hold none of the words.

    Filters narrow the articles before they are ranked:
    - `tags`: tag slugs, matching any of them. Call `tags` first for the slugs.
    - `kind`: `post`, `repo`, `paper` or `model`.
    - `since`: an ISO date, such as `2026-10-01`. Omit for all time.
    - `publisher`: a publisher slug, as a result's `publisher.slug` gives it.
    - `limit`: 1 to 100, default 20.

    Each result has `id`, `title`, `url`, `publisher`, `published_at`, `score`
    (1-100, how useful it is to someone building with AI), `summary`, `tags`
    and `excerpt`, about 300 characters of the text around the keywords. The
    full text is not returned: follow `url` to read the article.
    """
    if kind is not None and kind not in ArticleKind.__members__:
        raise ToolError(f"kind must be one of: {', '.join(ArticleKind.__members__)}")
    if limit < 1:
        raise ToolError("limit must be at least 1")
    try:
        since_at = datetime.fromisoformat(since) if since else None
    except ValueError:
        raise ToolError("since must be an ISO date, such as 2026-10-01")

    with Session(engine) as session:
        found = catalog.search(
            session,
            q,
            limit,
            tags=tags,
            kinds=[kind] if kind else None,
            since=since_at,
            publisher=publisher,
        )
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
        for article in found.data
    ]
