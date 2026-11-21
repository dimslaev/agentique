"""The `activate_publisher` tool: switch an inactive publisher on."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.features.curation import service as curation
from app.features.curation.model import SourceError


def activate_publisher(
    slug: str,
    reason: str,
    feed_url: str | None = None,
    search_domain: str | None = None,
) -> str:
    """Switch an inactive publisher on, so the nightly run polls it.

    Pass exactly one of `feed_url` (polled as RSS, or as Substack on a
    substack.com host) and `search_domain` (a lab or company with no feed,
    searched on its own site; must be the publisher's website host). The
    feed is read again first and refused if it has no post in 90 days.
    `reason` states the numbers, e.g. "probe 3/5 + 2/2 prior".
    """
    with Session(engine) as session:
        try:
            return curation.activate_publisher(
                session, slug, reason, feed_url, search_domain
            )
        except SourceError as exc:
            raise ToolError(str(exc))
