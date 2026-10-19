"""The `approve` tool: publish a candidate."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.curation import service as curation
from app.features.curation.model import CandidateError


def approve(
    url: str,
    score: int,
    reason: str,
    summary: str,
    kind: str,
    tags: list[str],
    publisher_kind: str | None = None,
    publisher_name: str | None = None,
) -> str:
    """Publish a candidate with the labels you chose, then embed it.

    `score` is 1-100 on the same scale the rubric describes, `reason` one short
    sentence naming what decided it, and `summary` the text a reader sees under
    the title. `kind` and `tags` (up to 3) come from `vocabulary`; a github,
    huggingface or arxiv URL sets its own kind. When the candidate's
    `publisher_kind` is `unknown`, pass `publisher_kind` (from
    `vocabulary`'s `publisher_kinds`) and, if its host is not a readable name,
    `publisher_name`; both are ignored for a publisher that has a kind. A label
    that is not in the vocabulary is refused and the candidate stays pending.
    The candidate stops being pending in the same transaction that inserts the
    article, so nothing is ever published twice.
    """
    require_write()
    with Session(engine) as session:
        try:
            article_id = curation.approve(
                session,
                url,
                score,
                reason,
                summary,
                kind,
                tags,
                publisher_kind,
                publisher_name,
            )
        except CandidateError as exc:
            raise ToolError(str(exc))
    return f"Published article #{article_id}: {url}"
