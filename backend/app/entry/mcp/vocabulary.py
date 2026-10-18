"""The `vocabulary` tool: the labels `approve` accepts."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.curation import service as curation


def vocabulary() -> dict[str, object]:
    """The labels `approve` accepts: `kinds`, `publisher_kinds`, and `tags` as
    slug -> description. Call it once per session, before the first approve."""
    require_write()
    with Session(engine) as session:
        return curation.vocabulary(session)
