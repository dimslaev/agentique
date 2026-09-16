"""What the curation agent does to a candidate: read it, approve it, reject it.

The nightly run ends at a `pending` row (`steps/queue.py`). This module is the
other end: the three verbs the agent drives it with, behind the MCP tools in
`app/mcp/tools.py`. Approving is the only thing in the codebase that writes an
Article now, so the whole insert-and-enrich tail lives here, reusing the
pipeline's own steps rather than a second copy of them.

A candidate is never half-published: the pending row is deleted in the same
transaction that inserts the Article, and enrichment (categories, tags,
embedding) is best-effort afterwards exactly as it is in the nightly run.
"""

from __future__ import annotations

from sqlmodel import Session, col, select

from app.catalog.models import Publisher
from app.platform.logging import log
from pipeline.fetching.extract_content import fetch_and_extract
from pipeline.models import Reject, RejectStage
from pipeline.steps.enrich import categorize_and_tag_articles, embed_articles
from pipeline.steps.persist import insert_articles
from pipeline.tags import load_vocabulary
from pipeline.types import Summarized

# What the agent triages on. Deliberately not the stored 2000 chars: a list of
# 80 candidates at full content is more than a reading pass can hold, and the
# agent asks for `get_content` on the ones worth a second look.
LIST_SNIPPET = 200
# How many pending rows one listing returns. A night queues tens, not hundreds;
# the cap is here so a backlog after a missed session comes back in readable
# pages rather than all at once.
LIST_LIMIT = 200
# How much of a re-fetched page is kept as the Article's content. Matches what
# the nightly run used to store before the scorer was replaced.
CONTENT_CAP = 20000


class CandidateError(Exception):
    """No pending candidate at that URL — approved already, rejected already,
    or never queued. The agent gets the message, not a traceback."""


def _pending(session: Session, url: str) -> Reject:
    row = session.get(Reject, url)
    if row is None:
        raise CandidateError(f"No candidate for {url}")
    if row.stage != RejectStage.pending:
        raise CandidateError(f"{url} is already {row.stage}, not pending")
    return row


def list_candidates(session: Session, limit: int = LIST_LIMIT) -> list[dict[str, str]]:
    """Every candidate waiting on a verdict, freshest first.

    One row per URL with what a triage pass needs and nothing more: the
    publisher and its trust tag, the traction the source reported, the dates,
    and the opening `LIST_SNIPPET` characters.
    """
    rows = session.exec(
        select(Reject, Publisher)
        .join(Publisher, col(Publisher.id) == col(Reject.publisher_id), isouter=True)
        .where(col(Reject.stage) == RejectStage.pending)
        .order_by(col(Reject.published_at).desc().nulls_last(), col(Reject.created_at))
        .limit(limit)
    ).all()

    return [
        {
            "url": r.url,
            "title": r.title or "",
            "source": r.source or "",
            "publisher": p.name if p else "",
            "trust": str(p.trust) if p else "",
            "traction": r.traction or "",
            "published_at": r.published_at.date().isoformat() if r.published_at else "",
            "queued_at": r.created_at.date().isoformat(),
            "snippet": (r.content or "")[:LIST_SNIPPET],
        }
        for r, p in rows
    ]


def get_content(session: Session, url: str) -> str:
    """The text the pipeline stored for one candidate.

    The fallback for a page the agent cannot fetch: a newsletter item has no
    web page of its own, and this is the only copy of what it said.
    """
    row = _pending(session, url)
    return row.content or ""


def _article_content(url: str, stored: str) -> str:
    """The best text available for the Article row.

    The ledger keeps only the first `rejects.CONTENT_CAP` characters, which is
    enough to judge by and too little to categorize and tag well, so the page is
    read again on approval. A fetch that fails or comes back shorter than what
    is already stored changes nothing — the stored text is never made worse.
    """
    try:
        fetched = fetch_and_extract(url, CONTENT_CAP)
    except Exception as e:
        log(f"  Re-fetch failed for {url}, keeping stored content: {e}")
        return stored
    return fetched if len(fetched) > len(stored) else stored


def approve(session: Session, url: str, score: int, reason: str, summary: str) -> int:
    """Turn a candidate into a published Article. Returns the new article's id.

    The agent's `score` and `reason` are stored on the Article exactly as the
    scorer's used to be, so the feed's ranking and the audit trail do not change
    shape. `summary` is what a reader sees under the title.
    """
    row = _pending(session, url)
    publisher = session.get(Publisher, row.publisher_id) if row.publisher_id else None
    if publisher is None or publisher.id is None:
        raise CandidateError(f"{url} has no publisher; cannot be published")

    item: Summarized = {
        "url": url,
        "title": row.title or "",
        "content": _article_content(url, row.content or ""),
        "published_date": row.published_at.isoformat() if row.published_at else None,
        "source": row.source or "",
        "publisher_id": publisher.id,
        "trust": str(publisher.trust),
        "publisher_kind": str(publisher.kind),
        "topic_gated": publisher.topic_gated,
        "score": score,
        "score_reason": reason,
        "summary": summary,
    }

    # Deleted before the insert commits, so the URL is a pending candidate or an
    # Article and never both: `filter_known_urls` reads either one.
    session.delete(row)
    inserted = insert_articles(session, [item])
    if not inserted:
        raise CandidateError(f"{url} could not be inserted")

    # Best-effort, as in the nightly run: a failure here costs a field, never
    # the article. Titles are not rewritten — the agent read the page and wrote
    # the summary, so a second model guessing at the title adds nothing.
    processed = categorize_and_tag_articles(session, inserted, load_vocabulary(session))
    embed_articles(session, processed)

    return inserted[0]["id"]


def reject(session: Session, url: str, score: int, reason: str) -> None:
    """Turn a candidate down. The row stays, carrying the agent's verdict.

    Same stage the scorer used, so one query still answers "what did we turn
    down and why" across both judges. These verdicts are the next labelled set —
    the reason is written for a human reading them back, not for a log.
    """
    row = _pending(session, url)
    row.stage = RejectStage.below_threshold
    row.score = score
    row.reason = reason
    session.add(row)
    session.commit()
    log(f"  Rejected [{score}/100] {url}: {reason}")
