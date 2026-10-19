"""The `stories` tool: pending candidates grouped by story.

Curation coverage, not the right rail's stories: the name is the curate
rubric's, and the rail's tools are `story_candidates`, `save_story` and
`close_story`.
"""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.curation import service as curation
from app.features.curation.model import Coverage


def stories(days: int = 7) -> list[Coverage]:
    """Group the pending candidates that are one story, with each other or with
    an article published in the last `days`.

    Only groups of two or more come back, largest first, each with its
    `members` (same row shape as `similar`, without the distance), `coverage`
    (distinct publishers) and `publishers`. A member at stage `published`
    means the feed already carries the story. Call it once, after triage.
    """
    require_write()
    with Session(engine) as session:
        return curation.stories(session, days)
