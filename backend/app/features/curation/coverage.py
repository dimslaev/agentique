"""The rows `similar` and `stories` compare a candidate against: the feed's
recent articles and the ledger, each with the vector or the text it embeds to.

The distance maths is in `app.core.embedding`; this module loads the rows and
counts who covers a story.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import numpy.typing as npt
from sqlmodel import Session, col, select

from app.core.db.article import Article
from app.core.db.ledger import Reject, RejectStage
from app.core.db.publisher import Publisher
from app.core.embedding import SNIPPET_CAP, embed_batch, to_embedding_text
from app.features.curation.model import CandidateError, Neighbour

# Stage `similar` and `stories` report for a row that is an Article.
PUBLISHED = "published"


def covering(
    publishers: list[str],
    distances: npt.NDArray[np.float32],
    own: str | None,
    cutoff: float,
) -> list[str]:
    """The distinct publishers within ``cutoff``, plus the candidate's own. Pure."""
    names = {p for p, d in zip(publishers, distances, strict=True) if d <= cutoff}
    if own:
        names.add(own)
    return sorted(n for n in names if n)


def publisher_names(session: Session) -> dict[int, str]:
    rows = session.exec(select(Publisher.id, Publisher.name)).all()
    return {pid: name for pid, name in rows if pid is not None}


def feed_rows(
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


def ledger_rows(
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


def target(
    session: Session, url: str, names: dict[int, str]
) -> tuple[Neighbour, npt.NDArray[np.float32]]:
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
