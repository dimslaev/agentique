"""The `disable_publisher` tool: switch a publisher off, with the reason."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.curation import service as curation
from app.features.curation.model import SourceError


def disable_publisher(slug: str, reason: str) -> str:
    """Switch a publisher off, or mark an inactive one whose probe failed.

    `reason` states the numbers, e.g. "probe 1/10 2026-11-21" or "no feed
    2026-11-21". The publisher stays out of `discovery_candidates` until it
    earns an approval after today.
    """
    require_write()
    with Session(engine) as session:
        try:
            return curation.disable_publisher(session, slug, reason)
        except SourceError as exc:
            raise ToolError(str(exc))
