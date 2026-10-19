"""The `get_content` tool: one page of a candidate's stored text."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.curation import service as curation
from app.features.curation.model import CandidateError, ContentPage


def get_content(
    url: str, offset: int = 0, limit: int = curation.PAGE_LIMIT
) -> ContentPage:
    """Return one page of the article text the pipeline extracted for a candidate.

    The stored text is what a page fetch returns, cut at 12000 characters, so
    read here first. Returns `text`, `offset`, `next_offset` (null on the last
    page — pass it back as `offset` to read on), `total` characters, and, on
    the first page only, `links`: the repo / model / paper / docs URLs the
    article body links, grouped. Fetch the page only when this is empty, a
    teaser, or cut off before the part you need.
    """
    require_write()
    with Session(engine) as session:
        try:
            return curation.get_content(session, url, offset, limit)
        except CandidateError as exc:
            raise ToolError(str(exc))
