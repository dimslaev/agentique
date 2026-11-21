"""The `week` tool: the week's published articles grouped into ranked topics,
and what readers liked."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.features.newsletter import service as newsletter
from app.features.newsletter.model import Week


def week(days: int = 7, limit: int = newsletter.WEEK_LIMIT) -> Week:
    """The weekly newsletter's material.

    `topics`: the last `days` of published articles grouped into topics, the
    most talked-about first. Ranked by `coverage` (distinct publishers
    carrying it, counting the copies curation rejected as retellings), then
    `likes`, then `top_score`; up to `limit` topics. Each topic's `articles`
    are the published ones - `url`, `title`, `publisher`, `publisher_kind`
    (`lab`, `company`, `individual`, `media`, `community`, `unknown`), `kind`,
    `score`, `likes`, and the `summary` curation wrote after reading it - and
    `covered_by` the other outlets' copies from the ledger, with curation's
    `reason`.

    `liked`: articles readers liked in the last `days`, however old, most
    likes in the window first. Same fields as an article, plus
    `published_at`.
    """
    with Session(engine) as session:
        return {
            "topics": newsletter.week(session, days, limit),
            "liked": newsletter.liked(session, days),
        }
