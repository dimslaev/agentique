"""The reject ledger: every URL the funnel turned down, with what it saw and why.

Two jobs. ``filter_known_urls`` reads it so a rejected URL is never fetched and
judged again. And it keeps the evidence - the text the scorer saw, the score,
the scorer's reason - so a reject can be audited, re-scored under a new rubric,
or used as a training negative instead of vanishing.

The embedding is deliberately not stored: it is a pure function of the stored
title and ``content[:SNIPPET_CAP]``, so it can be rebuilt offline in seconds.
"""

from __future__ import annotations

from sqlmodel import Session

from pipeline.freshness import parse_date
from pipeline.models import Reject, RejectStage
from pipeline.types import Candidate

# Enough to re-score with a longer input or re-embed with a better model later;
# the full body would make the ledger most of the database.
CONTENT_CAP = 2000


def _pg_text(text: str) -> str:
    # Postgres text columns reject NUL bytes, and fetched pages occasionally
    # carry one. The failed commit would take the whole source down with it.
    return text.replace("\x00", "")


def record_reject(
    session: Session,
    a: Candidate,
    stage: RejectStage,
    *,
    score: int | None = None,
    reason: str | None = None,
    detail: dict[str, object] | None = None,
) -> None:
    """Stage a reject row. The caller commits, as it did for the bare URL."""
    content = _pg_text(a["content"][:CONTENT_CAP])
    session.merge(
        Reject(
            url=a["url"],
            stage=stage,
            title=_pg_text(a["title"]),
            source=a["source"],
            publisher_id=a["publisher_id"],
            published_at=parse_date(a["published_date"]),
            content=content or None,
            traction=a.get("traction"),
            score=score,
            reason=reason,
            detail=detail,
        )
    )
