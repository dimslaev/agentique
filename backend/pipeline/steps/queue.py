"""Step 3: park what survived filtering as a candidate for the curation agent.

The last step of the nightly run. Nothing is scored, summarized or inserted
here: a candidate becomes a `pending` row in the reject ledger and waits to be
read. The agent (see `.claude/skills/curate/SKILL.md`) approves or rejects it
through the MCP tools in `app/mcp/tools.py`, and only an approval writes an
Article.

Why the ledger and not a table of its own: the row already holds everything a
judge needs — title, source, publisher, the first `CONTENT_CAP` chars, traction,
dates — and `filter_known_urls` already reads it, so a candidate waiting for the
agent is not re-fetched the next night. A `pending` row that is never read stays
pending; candidates wait, they are not dropped.
"""

from __future__ import annotations

from sqlmodel import Session

from app.platform.logging import log
from pipeline.models import RejectStage
from pipeline.rejects import record_reject
from pipeline.types import Candidate


def queue_candidates(session: Session, articles: list[Candidate]) -> list[Candidate]:
    """Write one `pending` row per candidate and return what was written.

    Committed here rather than left to the caller: a run that crashes in a
    later source must not lose the candidates this one found, and a re-queued
    URL merges onto its own row.
    """
    if not articles:
        return []

    for a in articles:
        record_reject(session, a, RejectStage.pending)
        log(f"  Queued candidate: {a['title'][:70]}")
    session.commit()

    log(f"  {len(articles)} candidates queued for review")
    return articles
