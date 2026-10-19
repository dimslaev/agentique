"""The `reject_many` tool: turn many candidates down, each on its own."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.curation import service as curation
from app.features.curation.model import Verdict


def reject_many(verdicts: list[Verdict]) -> str:
    """Turn down many candidates at once: each of `verdicts` is `{url, score,
    reason}`, the same fields `reject` takes.

    Each is settled on its own, so one URL that is not pending costs that line
    and not the batch. Returns one line per verdict, in order, saying whether
    it was rejected or why not.
    """
    require_write()
    with Session(engine) as session:
        return "\n".join(curation.reject_many(session, verdicts))
