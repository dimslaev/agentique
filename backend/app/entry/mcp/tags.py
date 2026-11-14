"""The `tags` tool: the tags articles carry, with how many carry each."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.features.catalog import service as catalog

# More than the vocabulary holds, so the list is whole.
MAX_TAGS = 1000


def tags() -> list[dict[str, object]]:
    """Every tag in agentique's archive, busiest first: `slug`, `name` and
    `count`, the number of articles that carry it.

    Call it before `search` to see what topics exist, then pass slugs as
    `search`'s `tags` filter.
    """
    with Session(engine) as session:
        facets = catalog.tag_facets(session, None, MAX_TAGS)
    return [facet.model_dump() for facet in facets]
