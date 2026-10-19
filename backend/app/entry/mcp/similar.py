"""The `similar` tool: what the feed and the ledger hold close to one candidate."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.curation import service as curation
from app.features.curation.model import CandidateError, Similar


def similar(url: str, days: int = 7, limit: int = 8) -> Similar:
    """Show what the feed and the ledger hold that is close to one candidate.

    Compares by embedding against every published article and every candidate
    or reject from the last `days`. `rows` lists up to `limit` neighbours, the
    closest first: `url`, `title`, `publisher`, `stage` (`published`,
    `pending`, or the reject stage), `score` and `distance` (under 0.30 is the
    same story). `coverage` is how many distinct publishers carry this story,
    this candidate's own included, with their names in `publishers`.
    """
    require_write()
    with Session(engine) as session:
        try:
            return curation.similar(session, url, days, limit)
        except CandidateError as exc:
            raise ToolError(str(exc))
