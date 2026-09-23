"""What the curation agent does to a candidate: read it, approve it, reject it.

The nightly run ends at a `pending` row (`steps/queue.py`). This module is the
other end: the three verbs the agent drives it with, behind the MCP tools in
`app/mcp/tools.py`. Approving is the only thing in the codebase that writes an
Article now, so the whole insert-and-enrich tail lives here, reusing the
pipeline's own steps rather than a second copy of them.

The agent read the page, so it writes everything a reader sees: the summary,
the categories, the kind and the tags. Approving makes no LLM call and no fetch;
the only enrichment left is the embedding, which is local and best-effort.

A candidate is never half-published: the pending row is deleted in the same
transaction that inserts the Article.
"""

from __future__ import annotations

from sqlmodel import Session, col, select

from app.catalog.models import Article, ArticleKind, Category, Publisher
from app.platform.logging import log
from pipeline.models import Reject, RejectStage
from pipeline.rejects import CONTENT_CAP
from pipeline.steps import SNIPPET_CAP
from pipeline.steps.enrich import embed_articles
from pipeline.steps.persist import insert_articles
from pipeline.tags import load_vocabulary, validate_tags, write_article_tags
from pipeline.types import Summarized
from pipeline.url_kind import kind_from_url

# What the agent triages on. Deliberately not the stored text: a list of 80
# candidates at full content is more than a reading pass can hold, and the
# agent asks for `get_content` on the ones worth a second look.
LIST_SNIPPET = 200
# How many pending rows one listing returns. A night queues tens, not hundreds;
# the cap is here so a backlog after a missed session comes back in readable
# pages rather than all at once.
LIST_LIMIT = 200


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
    """The article text the pipeline extracted for one candidate.

    Up to `rejects.CANDIDATE_CAP` characters, the same text the page fetch
    would return, so the agent reads from here and fetches only when it is
    missing or cut short.
    """
    row = _pending(session, url)
    return row.content or ""


def vocabulary(session: Session) -> dict[str, object]:
    """The labels `approve` accepts: categories, kinds, and the tag list with
    each tag's description. Read from the db, so a tag added there is offered
    the same night."""
    vocab = load_vocabulary(session)
    return {
        "categories": [c.value for c in Category],
        "kinds": [k.value for k in ArticleKind],
        "tags": dict(sorted(vocab.slug_to_description.items())),
    }


def _categories(raw: list[str]) -> list[Category]:
    valid = {c.value for c in Category}
    out = [Category(c.lower()) for c in raw if c.lower() in valid]
    if not out:
        raise CandidateError(f"No valid category in {raw}; pick from {sorted(valid)}")
    return list(dict.fromkeys(out))


def _kind(url: str, raw: str) -> ArticleKind:
    """The URL host wins when it is conclusive (a github.com link is a repo),
    whatever the agent said; otherwise the agent's kind must be a real one."""
    by_host = kind_from_url(url)
    if by_host:
        return by_host
    try:
        return ArticleKind(raw.lower())
    except ValueError:
        raise CandidateError(
            f"Unknown kind {raw!r}; pick from {[k.value for k in ArticleKind]}"
        )


def approve(
    session: Session,
    url: str,
    score: int,
    reason: str,
    summary: str,
    categories: list[str],
    kind: str,
    tags: list[str],
) -> int:
    """Turn a candidate into a published Article. Returns the new article's id.

    The agent's `score` and `reason` are stored on the Article exactly as the
    scorer's used to be, so the feed's ranking and the audit trail do not change
    shape. `summary` is what a reader sees under the title; `categories`,
    `kind` and `tags` come from `vocabulary`. Labels are checked before anything
    is written, so a bad one is a message and the candidate stays pending.
    """
    row = _pending(session, url)
    publisher = session.get(Publisher, row.publisher_id) if row.publisher_id else None
    if publisher is None or publisher.id is None:
        raise CandidateError(f"{url} has no publisher; cannot be published")

    vocab = load_vocabulary(session)
    checked_categories = _categories(categories)
    checked_kind = _kind(url, kind)
    slugs = validate_tags(tags, vocab.slugs)

    item: Summarized = {
        "url": url,
        "title": row.title or "",
        "content": row.content or "",
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

    [persisted] = inserted
    article = session.get(Article, persisted["id"])
    if article:
        article.categories = checked_categories
        article.kind = checked_kind
        session.add(article)
    write_article_tags(session, persisted["id"], slugs, vocab)
    session.commit()

    # Best-effort, as in the nightly run: a failed embedding costs the field,
    # never the article.
    embed_articles(
        session,
        [
            {
                "id": persisted["id"],
                "url": url,
                "title": persisted["title"],
                "score": score,
                "snippet": persisted["content"][:SNIPPET_CAP],
                "categories": checked_categories,
            }
        ],
    )

    return persisted["id"]


def reject(session: Session, url: str, score: int, reason: str) -> None:
    """Turn a candidate down. The row stays, carrying the agent's verdict.

    Same stage the scorer used, so one query still answers "what did we turn
    down and why" across both judges. These verdicts are the next labelled set —
    the reason is written for a human reading them back, not for a log. The
    content goes back to the settled-reject cap: the full text was for reading.
    """
    row = _pending(session, url)
    row.stage = RejectStage.below_threshold
    row.content = row.content[:CONTENT_CAP] if row.content else None
    row.score = score
    row.reason = reason
    session.add(row)
    session.commit()
    log(f"  Rejected [{score}/100] {url}: {reason}")
