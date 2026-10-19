"""The `reject` tool: turn one candidate down."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.curation import service as curation
from app.features.curation.model import CandidateError


def reject(url: str, score: int, reason: str) -> str:
    """Turn a candidate down, keeping the score and the reason for it.

    The row stays in the ledger so the URL is never judged twice, and so the
    verdicts can be read back as labels. Write `reason` for a human reading a
    hundred of them later, not for a log line.
    """
    require_write()
    with Session(engine) as session:
        try:
            curation.reject(session, url, score, reason)
        except CandidateError as exc:
            raise ToolError(str(exc))
    return f"Rejected [{score}/100] {url}"
