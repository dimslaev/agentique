"""What the curation agent does to a candidate: read it, compare it, approve it,
reject it.

The nightly run ends at a `pending` row (`steps/queue.py`). This module is the
other end: the verbs the agent drives it with, behind the MCP tools in
`app/mcp/tools.py`. Approving is the only thing in the codebase that writes an
Article now, so the whole insert-and-enrich tail lives here, reusing the
pipeline's own steps rather than a second copy of them.

The agent read the page, so it writes everything a reader sees: the summary,
the categories, the kind and the tags. Approving makes no LLM call and no fetch;
the only enrichment left is the embedding, which is local and best-effort.

A candidate is never half-published: the pending row is deleted in the same
transaction that inserts the Article.

Comparing is by embedding: `similar` and `stories` put a candidate beside what
the feed already carries and what else is queued, so the agent can tell a story
that three outlets covered from one only its publisher did. The distance maths
is pure numpy and kept apart from the queries, so it is tested on synthetic
vectors with no model load.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import NotRequired, TypedDict

import numpy as np
from sqlmodel import Session, col, func, select

from app.catalog.models import Article, ArticleKind, Category, Publisher
from app.platform.logging import log
from pipeline.embedding import embed_batch, to_embedding_text
from pipeline.models import Reject, RejectStage
from pipeline.rejects import CANDIDATE_CAP, CONTENT_CAP
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
# How far back a publisher's approval rate reaches. Long enough that a weekly
# blog has a record, short enough to follow a publisher that changed.
APPROVAL_WINDOW_DAYS = 90
# One page of `get_content`. Enough to triage on; an approval reads on to the end.
PAGE_LIMIT = 4000
# Two texts this close are the same story. Same-story pairs sit at 0.29-0.35
# with the potion-base-8M embeddings; tight on purpose, because coverage counts
# what falls under it and a loose cut inflates every story.
DEDUP_DIST_THRESHOLD = 0.30
# `similar` lists neighbours out to here: related enough to read the title, not
# close enough to count as the same story.
RELATED_DIST = 0.45
# Stage `similar` and `stories` report for a row that is an Article.
PUBLISHED = "published"


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


def list_candidates(session: Session, limit: int = LIST_LIMIT) -> list[dict[str, str]]:
    """Every candidate waiting on a verdict, freshest first.

    One row per URL with what a triage pass needs and nothing more: the
    publisher and its approval rate over `APPROVAL_WINDOW_DAYS`, the traction
    the source reported, the dates, and the opening `LIST_SNIPPET` characters.
    """
    rows = session.exec(
        select(Reject, Publisher)
        .join(Publisher, col(Publisher.id) == col(Reject.publisher_id), isouter=True)
        .where(col(Reject.stage) == RejectStage.pending)
        .order_by(col(Reject.published_at).desc().nulls_last(), col(Reject.created_at))
        .limit(limit)
    ).all()

    since = datetime.now(UTC) - timedelta(days=APPROVAL_WINDOW_DAYS)
    ids = list({r.publisher_id for r, _ in rows if r.publisher_id is not None})
    counts = approval_counts(session, ids, since)

    return [
        {
            "url": r.url,
            "title": r.title or "",
            "source": r.source or "",
            "publisher": p.name if p else "",
            "approved": approval_rate(*counts.get(r.publisher_id or 0, (0, 0))),
            "traction": r.traction or "",
            "published_at": r.published_at.date().isoformat() if r.published_at else "",
            "queued_at": r.created_at.date().isoformat(),
            "snippet": (r.content or "")[:LIST_SNIPPET],
        }
        for r, p in rows
    ]


class ContentPage(TypedDict):
    """One slice of a candidate's stored text. ``next_offset`` is None on the
    last page; ``links`` rides on the first page only."""

    text: str
    offset: int
    next_offset: int | None
    total: int
    links: NotRequired[dict[str, list[str]]]


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

    The stored text is up to `rejects.CANDIDATE_CAP` characters, the same text
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


class Neighbour(TypedDict):
    """A row beside a candidate: an Article (stage ``published``) or a ledger row."""

    url: str
    title: str
    publisher: str
    stage: str
    score: int | None
    distance: NotRequired[float]


class Similar(TypedDict):
    url: str
    # Distinct publishers carrying this story, the candidate's own included.
    coverage: int
    publishers: list[str]
    rows: list[Neighbour]


class Story(TypedDict):
    coverage: int
    publishers: list[str]
    members: list[Neighbour]


def cosine_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise cosine distance, rows of ``a`` against rows of ``b``. Pure."""
    if a.size == 0 or b.size == 0:
        return np.empty((a.shape[0], b.shape[0]), dtype=np.float32)
    a_norm = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)
    b_norm = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-12)
    return 1 - (a_norm @ b_norm.T)


def nearest(distances: np.ndarray, cutoff: float, limit: int) -> list[int]:
    """Indices of the closest rows within ``cutoff``, closest first. Pure."""
    order = np.argsort(distances, kind="stable")
    return [int(i) for i in order if distances[i] <= cutoff][: max(limit, 0)]


def covering(
    publishers: list[str], distances: np.ndarray, own: str | None, cutoff: float
) -> list[str]:
    """The distinct publishers within ``cutoff``, plus the candidate's own. Pure."""
    names = {p for p, d in zip(publishers, distances, strict=True) if d <= cutoff}
    if own:
        names.add(own)
    return sorted(n for n in names if n)


def story_groups(
    distances: np.ndarray, pending: list[bool], cutoff: float
) -> list[list[int]]:
    """Group rows that are the same story, with at least one pending row in each.

    ``distances`` is the square matrix over every row. An edge needs a pending
    row at one end or both, so two feed articles never join a group through each
    other and a chain of loosely related stories cannot grow through the feed.
    Returns only groups of two or more, largest first. Pure.
    """
    n = len(pending)
    parent = list(range(n))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        if not pending[i]:
            continue
        for j in range(n):
            if j != i and distances[i, j] <= cutoff:
                parent[root(j)] = root(i)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(root(i), []).append(i)
    found = [g for g in groups.values() if len(g) >= 2 and any(pending[i] for i in g)]
    return sorted(found, key=len, reverse=True)


def _publisher_names(session: Session) -> dict[int, str]:
    rows = session.exec(select(Publisher.id, Publisher.name)).all()
    return {pid: name for pid, name in rows if pid is not None}


def _feed_rows(
    session: Session, since: datetime, names: dict[int, str]
) -> tuple[list[Neighbour], list[list[float]]]:
    """Articles created since ``since`` that carry an embedding, and those
    embeddings."""
    articles = session.exec(
        select(Article).where(
            col(Article.created_at) >= since,
            col(Article.embedding).is_not(None),
        )
    ).all()
    out: list[Neighbour] = []
    vecs: list[list[float]] = []
    for a in articles:
        # pgvector hands back a numpy array, and bool(array) raises.
        if a.embedding is None:
            continue
        out.append(
            {
                "url": a.url,
                "title": a.title,
                "publisher": names.get(a.publisher_id, ""),
                "stage": PUBLISHED,
                "score": a.score,
            }
        )
        vecs.append(list(a.embedding))
    return out, vecs


def _ledger_rows(
    session: Session,
    names: dict[int, str],
    *,
    since: datetime | None = None,
    pending_only: bool = False,
) -> tuple[list[Neighbour], list[str]]:
    """Ledger rows and the text each one embeds to: the same title and
    ``SNIPPET_CAP`` characters an Article's stored embedding is built from."""
    query = select(Reject)
    if since is not None:
        query = query.where(col(Reject.created_at) >= since)
    if pending_only:
        query = query.where(col(Reject.stage) == RejectStage.pending)
    out: list[Neighbour] = []
    texts: list[str] = []
    for row in session.exec(query).all():
        out.append(
            {
                "url": row.url,
                "title": row.title or "",
                "publisher": names.get(row.publisher_id, "")
                if row.publisher_id
                else "",
                "stage": str(row.stage or ""),
                "score": row.score,
            }
        )
        texts.append(
            to_embedding_text(row.title or "", (row.content or "")[:SNIPPET_CAP])
        )
    return out, texts


def _target(
    session: Session, url: str, names: dict[int, str]
) -> tuple[Neighbour, np.ndarray]:
    """The row ``similar`` compares from, and its vector."""
    row = session.get(Reject, url)
    if row is not None:
        text = to_embedding_text(row.title or "", (row.content or "")[:SNIPPET_CAP])
        publisher = names.get(row.publisher_id, "") if row.publisher_id else ""
        target: Neighbour = {
            "url": url,
            "title": row.title or "",
            "publisher": publisher,
            "stage": str(row.stage or ""),
            "score": row.score,
        }
        return target, np.array(embed_batch([text])[0], dtype=np.float32)

    article = session.exec(select(Article).where(col(Article.url) == url)).first()
    if article is None:
        raise CandidateError(f"No candidate or article for {url}")
    published: Neighbour = {
        "url": url,
        "title": article.title,
        "publisher": names.get(article.publisher_id, ""),
        "stage": PUBLISHED,
        "score": article.score,
    }
    if article.embedding is not None:
        return published, np.array(article.embedding, dtype=np.float32)
    text = to_embedding_text(article.title, (article.content or "")[:SNIPPET_CAP])
    return published, np.array(embed_batch([text])[0], dtype=np.float32)


def similar(session: Session, url: str, days: int = 7, limit: int = 8) -> Similar:
    """What the feed and the ledger hold that is close to one candidate.

    Compares against every Article and every ledger row (any stage) created in
    the last ``days``. Rows are listed out to ``RELATED_DIST``, closest first;
    ``coverage`` counts the distinct publishers within
    ``DEDUP_DIST_THRESHOLD``, the candidate's own included, over every row in
    the window rather than just the listed ones.
    """
    names = _publisher_names(session)
    target, target_vec = _target(session, url, names)
    since = datetime.now(UTC) - timedelta(days=days)

    feed, feed_vecs = _feed_rows(session, since, names)
    ledger, ledger_texts = _ledger_rows(session, names, since=since)
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
    publishers = covering(
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


def stories(session: Session, days: int = 7) -> list[Story]:
    """The pending candidates that are one story, with each other or with
    something the feed published in the last ``days``.

    Only groups of two or more come back, largest first. A group with no
    Article in it is a story several outlets are carrying tonight; a group with
    one is a story the feed already has.
    """
    names = _publisher_names(session)
    since = datetime.now(UTC) - timedelta(days=days)

    queued, queued_texts = _ledger_rows(session, names, pending_only=True)
    if not queued:
        return []
    feed, feed_vecs = _feed_rows(session, since, names)

    rows = queued + feed
    vecs = np.array(embed_batch(queued_texts) + feed_vecs, dtype=np.float32)
    pending = [True] * len(queued) + [False] * len(feed)
    groups = story_groups(cosine_distances(vecs, vecs), pending, DEDUP_DIST_THRESHOLD)

    out: list[Story] = []
    for group in groups:
        members = [rows[i] for i in group]
        publishers = sorted({m["publisher"] for m in members if m["publisher"]})
        out.append(
            {"coverage": len(publishers), "publishers": publishers, "members": members}
        )
    return out


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


class Verdict(TypedDict):
    """One rejection in a `reject_many` batch."""

    url: str
    score: int
    reason: str


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
