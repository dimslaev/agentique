"""What the curation agent does to a candidate: read it, compare it, approve it,
reject it.

The nightly collect run ends at a `pending` row. This module is the other end:
the verbs the agent drives it with, behind the MCP tools in `app/mcp/tools.py`.
Approving is the only thing in the codebase that writes an Article, so the
insert-and-embed tail (`publish.py`) belongs to curation alone.

The agent read the page, so it writes everything a reader sees: the summary,
the kind and the tags, and the kind of a publisher the pipeline has only just
created for a new site. Approving makes no LLM call and no fetch;
the only enrichment left is the embedding, which is local and best-effort.

A candidate is never half-published: the pending row is deleted in the same
transaction that inserts the Article.

Comparing is by embedding: `similar` and `stories` put a candidate beside what
the feed already carries and what else is queued, so the agent can tell a story
that three outlets covered from one only its publisher did. The distance maths
is pure numpy in `app.core.embedding`, and the row loading is in `coverage.py`,
so the maths is tested on synthetic vectors with no model load.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
from sqlmodel import Session, col, func, select

from app.core.db.article import Article, ArticleKind, kind_from_url
from app.core.db.ledger import CANDIDATE_CAP, CONTENT_CAP, Reject, RejectStage
from app.core.db.publisher import Publisher, PublisherKind
from app.core.embedding import (
    DEDUP_DIST_THRESHOLD,
    RELATED_DIST,
    SNIPPET_CAP,
    cosine_distances,
    embed_batch,
    nearest,
    story_groups,
)
from app.core.logging import log
from app.features.curation import coverage
from app.features.curation.model import (
    CandidateError,
    CandidatePage,
    ContentPage,
    Coverage,
    Neighbour,
    Similar,
    Summarized,
    Verdict,
)
from app.features.curation.publish import embed_articles, insert_articles
from app.features.curation.tags import (
    load_vocabulary,
    validate_tags,
    write_article_tags,
)

# What the agent triages on. Deliberately not the stored text: a list of 80
# candidates at full content is more than a reading pass can hold, and the
# agent asks for `get_content` on the ones worth a second look.
LIST_SNIPPET = 200
# How many pending rows one page of `list_candidates` returns. A night queues
# over 150, which at ~500 characters a row is more than one tool result may
# carry; 50 keeps a page near 7k tokens.
LIST_LIMIT = 50
# How far back a publisher's approval rate reaches. Long enough that a weekly
# blog has a record, short enough to follow a publisher that changed.
APPROVAL_WINDOW_DAYS = 90
# One page of `get_content`. Enough to triage on; an approval reads on to the end.
PAGE_LIMIT = 4000


def _pending(session: Session, url: str) -> Reject:
    row = session.get(Reject, url)
    if row is None:
        raise CandidateError(f"No candidate for {url}")
    if row.stage != RejectStage.pending:
        raise CandidateError(f"{url} is already {row.stage}, not pending")
    return row


def approval_rate(approved: int, rejected: int) -> str:
    """A publisher's record as the agent reads it: "3/10", or "new". Pure."""
    decided = approved + rejected
    return f"{approved}/{decided}" if decided else "new"


def approval_counts(
    session: Session, publisher_ids: list[int], since: datetime
) -> dict[int, tuple[int, int]]:
    """``{publisher_id: (approved, rejected)}`` for verdicts since ``since``.

    An approval is an Article, a rejection a `below_threshold` row. Both are
    dated by when the candidate was queued, which is within a night of when it
    was judged.
    """
    if not publisher_ids:
        return {}
    approved = session.exec(
        select(col(Article.publisher_id), func.count())
        .where(
            col(Article.publisher_id).in_(publisher_ids),
            col(Article.created_at) >= since,
        )
        .group_by(col(Article.publisher_id))
    ).all()
    rejected = session.exec(
        select(col(Reject.publisher_id), func.count())
        .where(
            col(Reject.publisher_id).in_(publisher_ids),
            col(Reject.stage) == RejectStage.below_threshold,
            col(Reject.created_at) >= since,
        )
        .group_by(col(Reject.publisher_id))
    ).all()
    counts: dict[int, tuple[int, int]] = {}
    for pid, n in approved:
        counts[pid] = (n, 0)
    for pid, n in rejected:
        if pid is not None:
            counts[pid] = (counts.get(pid, (0, 0))[0], n)
    return counts


def list_candidates(
    session: Session, offset: int = 0, limit: int = LIST_LIMIT
) -> CandidatePage:
    """One page of the candidates waiting on a verdict, freshest first.

    One row per URL with what a triage pass needs and nothing more: the
    publisher, its kind (`unknown` for a site the pipeline has just created
    one for) and its approval rate over `APPROVAL_WINDOW_DAYS`, the traction
    the source reported, the dates, and the opening `LIST_SNIPPET` characters.

    Paged by offset, so a verdict shifts every page after it: read all the
    pages before settling any candidate.
    """
    pending = col(Reject.stage) == RejectStage.pending
    total = session.exec(select(func.count()).select_from(Reject).where(pending)).one()
    start = min(max(offset, 0), total)
    size = min(max(limit, 1), LIST_LIMIT)
    rows = session.exec(
        select(Reject, Publisher)
        .join(Publisher, col(Publisher.id) == col(Reject.publisher_id), isouter=True)
        .where(pending)
        .order_by(
            col(Reject.published_at).desc().nulls_last(),
            col(Reject.created_at),
            col(Reject.url),
        )
        .offset(start)
        .limit(size)
    ).all()

    since = datetime.now(UTC) - timedelta(days=APPROVAL_WINDOW_DAYS)
    ids = list({r.publisher_id for r, _ in rows if r.publisher_id is not None})
    counts = approval_counts(session, ids, since)

    end = start + len(rows)
    return {
        "rows": [
            {
                "url": r.url,
                "title": r.title or "",
                "source": r.source or "",
                "publisher": p.name if p else "",
                "publisher_kind": p.kind.value if p else "",
                "approved": approval_rate(*counts.get(r.publisher_id or 0, (0, 0))),
                "traction": r.traction or "",
                "published_at": r.published_at.date().isoformat()
                if r.published_at
                else "",
                "queued_at": r.created_at.date().isoformat(),
                "snippet": (r.content or "")[:LIST_SNIPPET],
            }
            for r, p in rows
        ],
        "offset": start,
        "next_offset": end if end < total else None,
        "total": total,
    }


def page_bounds(total: int, offset: int, limit: int) -> tuple[int, int]:
    """``(start, end)`` of one page of a ``total``-char text. Pure.

    A negative offset reads from the start, a limit is at least one character
    and at most the whole stored text, and an offset past the end is an empty
    page rather than an error.
    """
    start = min(max(offset, 0), total)
    size = min(max(limit, 1), CANDIDATE_CAP)
    return start, min(start + size, total)


def get_content(
    session: Session, url: str, offset: int = 0, limit: int = PAGE_LIMIT
) -> ContentPage:
    """One page of the article text the pipeline extracted for a candidate.

    The stored text is up to `ledger.CANDIDATE_CAP` characters, the same text
    a page fetch would return, so the agent reads from here and fetches only
    when it is missing or cut short.
    """
    row = _pending(session, url)
    text = row.content or ""
    start, end = page_bounds(len(text), offset, limit)
    page: ContentPage = {
        "text": text[start:end],
        "offset": start,
        "next_offset": end if end < len(text) else None,
        "total": len(text),
    }
    if start == 0:
        page["links"] = row.links or {}
    return page


# ─── Similar and stories ─────────────────────────────────────────────────────


def similar(session: Session, url: str, days: int = 7, limit: int = 8) -> Similar:
    """What the feed and the ledger hold that is close to one candidate.

    Compares against every Article and every ledger row (any stage) created in
    the last ``days``. Rows are listed out to ``RELATED_DIST``, closest first;
    ``coverage`` counts the distinct publishers within
    ``DEDUP_DIST_THRESHOLD``, the candidate's own included, over every row in
    the window rather than just the listed ones.
    """
    names = coverage.publisher_names(session)
    target, target_vec = coverage.target(session, url, names)
    since = datetime.now(UTC) - timedelta(days=days)

    feed, feed_vecs = coverage.feed_rows(session, since, names)
    ledger, ledger_texts = coverage.ledger_rows(session, names, since=since)
    ledger_vecs = embed_batch(ledger_texts)

    rows = [r for r in feed + ledger if r["url"] != url]
    vecs = [
        v
        for r, v in zip(feed + ledger, feed_vecs + ledger_vecs, strict=True)
        if r["url"] != url
    ]
    if not rows:
        return {
            "url": url,
            "coverage": 1,
            "publishers": [target["publisher"]],
            "rows": [],
        }

    distances = cosine_distances(target_vec[None, :], np.array(vecs, dtype=np.float32))[
        0
    ]
    publishers = coverage.covering(
        [r["publisher"] for r in rows],
        distances,
        target["publisher"],
        DEDUP_DIST_THRESHOLD,
    )
    listed: list[Neighbour] = []
    for i in nearest(distances, RELATED_DIST, limit):
        row = Neighbour(**rows[i])
        row["distance"] = round(float(distances[i]), 3)
        listed.append(row)
    return {
        "url": url,
        "coverage": len(publishers),
        "publishers": publishers,
        "rows": listed,
    }


def stories(session: Session, days: int = 7) -> list[Coverage]:
    """The pending candidates that are one story, with each other or with
    something the feed published in the last ``days``.

    Only groups of two or more come back, largest first. A group with no
    Article in it is a story several outlets are carrying tonight; a group with
    one is a story the feed already has.
    """
    names = coverage.publisher_names(session)
    since = datetime.now(UTC) - timedelta(days=days)

    queued, queued_texts = coverage.ledger_rows(session, names, pending_only=True)
    if not queued:
        return []
    feed, feed_vecs = coverage.feed_rows(session, since, names)

    rows = queued + feed
    vecs = np.array(embed_batch(queued_texts) + feed_vecs, dtype=np.float32)
    pending = [True] * len(queued) + [False] * len(feed)
    groups = story_groups(cosine_distances(vecs, vecs), pending, DEDUP_DIST_THRESHOLD)

    out: list[Coverage] = []
    for group in groups:
        members = [rows[i] for i in group]
        publishers = sorted({m["publisher"] for m in members if m["publisher"]})
        out.append(
            {"coverage": len(publishers), "publishers": publishers, "members": members}
        )
    return out


# What the agent may call a publisher. `community` is for the aggregators,
# which are set up by hand; `unknown` is what it is being asked to replace.
NAMEABLE_KINDS = (
    PublisherKind.lab,
    PublisherKind.company,
    PublisherKind.individual,
    PublisherKind.media,
)


def vocabulary(session: Session) -> dict[str, object]:
    """The labels `approve` accepts: kinds, publisher kinds, and the tag list
    with each tag's description. Read from the db, so a tag added there is
    offered the same night."""
    vocab = load_vocabulary(session)
    return {
        "kinds": [k.value for k in ArticleKind],
        "publisher_kinds": [k.value for k in NAMEABLE_KINDS],
        "tags": dict(sorted(vocab.slug_to_description.items())),
    }


def _publisher_kind(publisher: Publisher, raw: str | None) -> PublisherKind | None:
    """The kind to give a publisher still `unknown`, None for one that already
    has a kind: once set it stays, so the agent cannot relabel a publisher
    differently from one night to the next."""
    if publisher.kind != PublisherKind.unknown:
        return None
    names = [k.value for k in NAMEABLE_KINDS]
    if not raw:
        raise CandidateError(
            f"{publisher.name} is a new publisher; pass publisher_kind, one of {names}"
        )
    if raw.lower() not in names:
        raise CandidateError(f"Unknown publisher_kind {raw!r}; pick from {names}")
    return PublisherKind(raw.lower())


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
    kind: str,
    tags: list[str],
    publisher_kind: str | None = None,
    publisher_name: str | None = None,
) -> int:
    """Turn a candidate into a published Article. Returns the new article's id.

    The agent's `score` and `reason` are stored on the Article exactly as the
    scorer's used to be, so the feed's ranking and the audit trail do not change
    shape. `summary` is what a reader sees under the title; `kind` and `tags`
    come from `vocabulary`. A publisher still `unknown` needs `publisher_kind`,
    and may take a `publisher_name` in place of its host; both are ignored for
    one that already has a kind. Labels are checked before anything is written,
    so a bad one is a message and the candidate stays pending.
    """
    row = _pending(session, url)
    publisher = session.get(Publisher, row.publisher_id) if row.publisher_id else None
    if publisher is None or publisher.id is None:
        raise CandidateError(f"{url} has no publisher; cannot be published")

    vocab = load_vocabulary(session)
    checked_kind = _kind(url, kind)
    slugs = validate_tags(tags, vocab.slugs)
    new_publisher_kind = _publisher_kind(publisher, publisher_kind)

    item: Summarized = {
        "url": url,
        "title": row.title or "",
        "content": row.content or "",
        "published_date": row.published_at.isoformat() if row.published_at else None,
        "source": row.source or "",
        "publisher_id": publisher.id,
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
        article.kind = checked_kind
        # The aggregator that found it; a feed's own item is its source.
        if row.source and row.source != publisher.name:
            article.found_via = row.source
        session.add(article)
    if new_publisher_kind is not None:
        publisher.kind = new_publisher_kind
        if publisher_name and publisher_name.strip():
            publisher.name = publisher_name.strip()
        session.add(publisher)
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


def reject_many(session: Session, verdicts: list[Verdict]) -> list[str]:
    """Turn down many candidates, each one settled on its own.

    One line back per verdict, in order. A URL that is not pending, or a write
    that fails, costs that line and nothing else: the rest are still rejected.
    """
    lines: list[str] = []
    for v in verdicts:
        try:
            reject(session, v["url"], v["score"], v["reason"])
        except CandidateError as exc:
            lines.append(f"Skipped {v['url']}: {exc}")
        except Exception as exc:
            session.rollback()
            lines.append(f"Failed {v['url']}: {type(exc).__name__}: {exc}")
        else:
            lines.append(f"Rejected [{v['score']}/100] {v['url']}")
    return lines
