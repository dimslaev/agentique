"""The `related` tool: what else covers one published article's subject."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.newsletter import service as newsletter
from app.features.newsletter.model import DigestError, Related


def related(
    url: str, days: int = newsletter.RELATED_DAYS, limit: int = newsletter.RELATED_LIMIT
) -> Related:
    """What else covers one published article's subject: the individual writer
    who tried it, the repo built on it, the commentary on it.

    Compares by embedding against every article from the last `days` and every
    reject from that window that scored 35 or more. Up to `limit` rows, the
    closest first: `url`, `title`, `publisher`, `publisher_kind`, `kind`,
    `stage` (`published` or `rejected`), `score`, `distance` (under 0.30 is the
    same story, up to 0.45 is the same subject), and `summary` for a published
    row or curation's `reason` for a rejected one.
    """
    require_write()
    with Session(engine) as session:
        try:
            return newsletter.related(session, url, days, limit)
        except DigestError as exc:
            raise ToolError(str(exc))
