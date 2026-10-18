"""The `story_candidates` tool: open stories and the clusters no story holds yet."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.stories import service as story_domain
from app.features.stories.model import Candidates


def story_candidates(days: int = 14) -> Candidates:
    """What the stories routine decides from.

    `open`: every open story, the most recently active first, with `slug`,
    `name`, `blurb`, `article_count`, `quiet_days` (since its newest article
    was published) and its newest 5 `articles`. `clusters`: the last `days`
    of published articles that sit in no open story, grouped by embedding at
    a looser cut than coverage, the most publishers first. Each cluster has
    `articles` (`url`, `title`, `publisher`, `published_at`, `score`,
    `summary`), its `publishers`, and `near`: the open stories one of its
    articles is close to. A single article close to a story comes back as a
    cluster of one with that story in `near`.
    """
    require_write()
    with Session(engine) as session:
        return story_domain.story_candidates(session, days)
