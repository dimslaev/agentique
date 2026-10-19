"""The `list_candidates` tool: one page of the pending queue."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.curation import service as curation
from app.features.curation.model import CandidatePage


def list_candidates(offset: int = 0, limit: int = curation.LIST_LIMIT) -> CandidatePage:
    """List one page of the articles waiting on a curation verdict, freshest first.

    Returns `rows`, `offset`, `next_offset` (null on the last page — pass it
    back as `offset` for the next one) and `total` pending. Pages hold at most
    50 rows. Read every page before settling any candidate: a verdict removes
    its row and shifts the pages after it.

    One row per candidate: `url`, `title`, `source` (where the link was found),
    `publisher`, `publisher_kind` (`unknown` for a site the pipeline has just
    created a publisher for: `approve` then needs one), `approved` (the
    publisher's approvals / decisions over the
    last 90 days, e.g. "3/10", or "new" when it has none), `traction`,
    `published_at`, `queued_at`, and a 200-character `snippet`. Deliberately not the full text — call
    `get_content` for a candidate worth a closer look.

    A candidate stays listed until `approve` or `reject` is called on it, so a
    session that stops halfway leaves the rest for the next one.
    """
    require_write()
    with Session(engine) as session:
        return curation.list_candidates(session, offset, limit)
