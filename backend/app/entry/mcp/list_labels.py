"""The `list_labels` tool: the labels `approve_article` accepts."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.features.curation import service as curation


def list_labels() -> dict[str, object]:
    """The labels `approve_article` accepts: `kinds`, `publisher_kinds`, and `tags` as
    slug -> description. Call it once per session, before the first approve."""
    with Session(engine) as session:
        return curation.list_labels(session)
