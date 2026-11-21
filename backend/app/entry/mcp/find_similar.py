"""The `find_similar` tool: what the feed and past decisions hold close to one URL."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.features.curation import service as curation
from app.features.curation.model import CandidateError, Similar


def find_similar(url: str, days: int = 7, limit: int = 8) -> Similar:
    """Show what the feed and past decisions hold that is close to one candidate or
    published article.

    Compares by embedding against every published article and every candidate
    or reject from the last `days`; pass `days=30` to reach the review or repo
    that came weeks after a release. `rows` lists up to `limit` neighbours, the
    closest first: `url`, `title`, `publisher`, `stage` (`published`,
    `pending`, or the reject stage), `score` and `distance` (under 0.30 is the
    same story). `publisher_count` is how many distinct publishers carry this story,
    this URL's own included, with their names in `publishers`.
    """
    with Session(engine) as session:
        try:
            return curation.find_similar(session, url, days, limit)
        except CandidateError as exc:
            raise ToolError(str(exc))
