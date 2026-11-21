"""The `coverage` tool: pending candidates grouped by story."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.features.curation import service as curation
from app.features.curation.model import Coverage


def coverage(days: int = 7) -> list[Coverage]:
    """Group the pending candidates that are one story, with each other or with
    an article published in the last `days`.

    Only groups of two or more come back, largest first, each with its
    `members` (same row shape as `similar`, without the distance), `coverage`
    (distinct publishers) and `publishers`. A member at stage `published`
    means the feed already carries the story. Call it once, after triage.
    """
    with Session(engine) as session:
        return curation.coverage_groups(session, days)
