"""The `queue_candidate` tool: hand one URL to the next curation run."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.features.collect import service as collect
from app.features.collect.model import QueueError


def queue_candidate(url: str, reason: str) -> str:
    """Queue a URL we never saw as a pending candidate, so the next curation
    run judges it.

    Refused when the URL is already an article or in the reject ledger, or when
    the page has no readable text or title. The page is read for the title,
    text and date, and the publisher is the site the URL is on (a new one is
    made inactive, as the nightly run makes it). `reason` names the competitor
    and where it ran the story, e.g. "AINews top story 2026-11-20"; the
    curation agent reads it as the candidate's traction, and the article keeps
    "Competitor watch" as `found_via` if approved.
    """
    with Session(engine) as session:
        try:
            queued = collect.queue_link(session, url, reason)
        except QueueError as exc:
            raise ToolError(str(exc))
    return f"Queued {queued['url']}: {queued['title']}"
