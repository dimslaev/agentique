"""The `week` tool: the week's published articles grouped into ranked topics."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.newsletter import service as digest
from app.features.newsletter.model import WeekTopic


def week(days: int = 7, limit: int = digest.WEEK_LIMIT) -> list[WeekTopic]:
    """The weekly newsletter's material: the last `days` of published articles
    grouped into topics, the most talked-about first.

    Ranked by `coverage` (distinct publishers carrying it, counting the copies
    curation rejected as retellings), then `likes`, then `top_score`; up to
    `limit` topics. Each topic's `articles` are the published ones - `url`,
    `title`, `publisher`, `publisher_kind` (`lab`, `company`, `individual`,
    `media`, `community`, `unknown`), `kind`, `score`, `likes`, and the `summary` curation
    wrote after reading it - and `covered_by` the other outlets' copies from
    the ledger, with curation's `reason`.
    """
    require_write()
    with Session(engine) as session:
        return digest.week(session, days, limit)
