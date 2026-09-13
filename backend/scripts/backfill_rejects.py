"""Backfill the evidence on rejects that predate it: fetch each page, then score it.

One-off, not part of pipeline/run.py. Rejects recorded before 2026-09-13 carry
only a URL and the time it was turned down. For each, this fetches the page
again for a title, text and date, matches the publisher by host, and runs the
pipeline's ScoreArticles prompt on title + the first SNIPPET_CAP chars - the
input a nightly run scores on. The score is today's verdict under today's
rubric, not the one that dropped the URL. Which step dropped it cannot be
recovered, so ``stage`` stays null and ``detail`` records the backfill.
``created_at``, the rejection time, is never touched.

Prints only by default; --write persists. With --write it resumes: it picks
rows where both ``stage`` and ``detail`` are null, and every row it finishes -
a page that could not be fetched included - gets ``detail`` set, so a rerun
carries on where the last one stopped. A failed scoring call writes nothing for
its batch, which the next run picks up again.

    cd backend && uv run --env-file ../.env python -m scripts.backfill_rejects --limit 10
    cd backend && uv run --env-file ../.env python -m scripts.backfill_rejects --write

The residential proxy is metered, so it only runs with --proxy. To retry the
pages that could not be fetched:
``UPDATE scored_url SET detail = NULL WHERE detail->>'fetch_failed' = 'true'``.
A reject that now clears the threshold is listed at the end rather than
inserted: whether the pipeline wrongly dropped it is a call for a human.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import NamedTuple

from sqlalchemy import literal, tuple_
from sqlmodel import Session, col, func, select
from trafilatura import extract_metadata

from app.catalog.models import LinkPlatform, Publisher
from app.platform.dates import get_datetime_utc
from app.platform.db import engine
from app.platform.logging import short_error, wait_ms
from baml_client.types import ArticleInput
from pipeline.fetching.extract_content import extract_text
from pipeline.fetching.http import (
    BROWSER_HEADERS,
    RESIDENTIAL_PROXY_URL,
    fetch_with_timeout,
)
from pipeline.freshness import parse_date
from pipeline.llm_text import sanitize_llm_text
from pipeline.models import Reject
from pipeline.rejects import CONTENT_CAP
from pipeline.steps import SNIPPET_CAP
from pipeline.steps.score import SCORE_BATCH, SCORE_BATCH_PAUSE_MS, SCORE_THRESHOLD
from pipeline.urls import hostname
from scripts.rescoring import (
    DEFAULT_MODEL,
    MAX_FAILED_BATCHES_IN_A_ROW,
    MODELS,
    score_batch,
)

DRY_RUN_LIMIT = 10
FETCH_TIMEOUT_SECS = 10.0
PROXY_TIMEOUT_SECS = 20.0
FETCH_CONCURRENCY = 5

# Hosts many unrelated authors publish under: a URL on one says nothing about
# which publisher it came from, so none is matched there.
SHARED_HOSTS = {
    "github.com",
    "linkedin.com",
    "medium.com",
    "reddit.com",
    "substack.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}


class Page(NamedTuple):
    title: str
    text: str
    published: str | None


def _get_html(url: str, proxy: str | None) -> str:
    try:
        resp = fetch_with_timeout(
            url,
            timeout=PROXY_TIMEOUT_SECS if proxy else FETCH_TIMEOUT_SECS,
            proxy=proxy,
            headers=BROWSER_HEADERS,
        )
    except Exception:
        return ""
    if not resp.is_success or "text/html" not in resp.headers.get("content-type", ""):
        return ""
    return resp.text


def fetch_page(url: str, use_proxy: bool) -> Page | None:
    """Title, readable text and date of a page, or None if nothing usable came
    back. Postgres refuses NUL bytes in text, so they are stripped here."""
    html = _get_html(url, None)
    if not html and use_proxy and RESIDENTIAL_PROXY_URL:
        html = _get_html(url, RESIDENTIAL_PROXY_URL)
    if not html:
        return None
    meta = extract_metadata(html, default_url=url)
    title = (meta.title or "").replace("\x00", "").strip()
    text = extract_text(html).replace("\x00", "")
    if not title and not text:
        return None
    return Page(title=title or url, text=text, published=meta.date)


def publishers_by_host(session: Session) -> dict[str, Publisher]:
    """Host -> the one publisher whose links name it. A host two publishers
    share is left out: it cannot say which of them a URL belongs to."""
    candidates: dict[str, dict[int, Publisher]] = {}
    for p in session.exec(select(Publisher)).all():
        for platform, link in p.links.items():
            if platform == LinkPlatform.search:
                host = link.lower().removeprefix("www.")
            elif platform in (
                LinkPlatform.website,
                LinkPlatform.rss,
                LinkPlatform.substack,
            ):
                host = hostname(link)
            else:
                continue
            if host and host not in SHARED_HOSTS and p.id is not None:
                candidates.setdefault(host, {})[p.id] = p
    return {
        host: next(iter(pubs.values()))
        for host, pubs in candidates.items()
        if len(pubs) == 1
    }


def match_publisher(url: str, by_host: dict[str, Publisher]) -> Publisher | None:
    """The publisher for a URL's host, climbing to parent domains
    (blog.example.com -> example.com) until one matches."""
    host = hostname(url)
    while "." in host:
        if host in by_host:
            return by_host[host]
        host = host.partition(".")[2]
    return None


def count_pending(session: Session) -> int:
    return session.exec(
        select(func.count())
        .select_from(Reject)
        .where(col(Reject.stage).is_(None), col(Reject.detail).is_(None))
    ).one()


def pick_batch(
    session: Session, before: tuple[datetime, str] | None, size: int
) -> list[Reject]:
    """The next pending rejects, newest first - the likeliest to still be up.
    Walking a (created_at, url) cursor keeps a batch that failed this run from
    being picked again until the next run."""
    stmt = select(Reject).where(
        col(Reject.stage).is_(None), col(Reject.detail).is_(None)
    )
    if before is not None:
        stmt = stmt.where(
            tuple_(col(Reject.created_at), col(Reject.url))
            < tuple_(literal(before[0]), literal(before[1]))
        )
    stmt = stmt.order_by(col(Reject.created_at).desc(), col(Reject.url).desc())
    return list(session.exec(stmt.limit(size)).all())


def to_input(reject: Reject, page: Page, publisher: Publisher | None) -> ArticleInput:
    return ArticleInput(
        url=reject.url,
        title=page.title,
        source=publisher.name if publisher else hostname(reject.url),
        snippet=page.text[:SNIPPET_CAP] or None,
        trust=str(publisher.trust) if publisher else "medium",
        # When it was rejected, not today: "old" means old when we saw it.
        seen_on=reject.created_at.date().isoformat(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model", choices=sorted(MODELS), default=DEFAULT_MODEL)
    parser.add_argument(
        "--limit",
        type=int,
        help=f"rejects to handle this run (default: all with --write, "
        f"{DRY_RUN_LIMIT} without)",
    )
    parser.add_argument(
        "--write", action="store_true", help="persist the backfill (default: print)"
    )
    parser.add_argument(
        "--proxy",
        action="store_true",
        help="retry failed fetches via the metered proxy",
    )
    args = parser.parse_args()
    write: bool = args.write
    model: str = args.model
    use_proxy: bool = args.proxy
    limit: int | None = args.limit
    if limit is None and not write:
        limit = DRY_RUN_LIMIT

    today = get_datetime_utc().date().isoformat()
    before: tuple[datetime, str] | None = None
    taken = scored = unfetched = unanswered = 0
    failed_in_a_row = 0
    now_passing: list[tuple[int, str, str]] = []
    with Session(engine) as session:
        by_host = publishers_by_host(session)
        mode = "writing" if write else "dry run, nothing is written"
        print(f"{count_pending(session)} rejects to backfill with {model} ({mode})")
        try:
            while limit is None or taken < limit:
                size = SCORE_BATCH if limit is None else min(SCORE_BATCH, limit - taken)
                rejects = pick_batch(session, before, size)
                if not rejects:
                    break
                before = (rejects[-1].created_at, rejects[-1].url)
                taken += len(rejects)

                with ThreadPoolExecutor(max_workers=FETCH_CONCURRENCY) as pool:
                    pages = list(
                        pool.map(lambda r: fetch_page(r.url, use_proxy), rejects)
                    )

                fetched: list[tuple[Reject, Page, Publisher | None]] = []
                for reject, page in zip(rejects, pages, strict=True):
                    if page is None:
                        unfetched += 1
                        print(f"  --- unfetchable: {reject.url}")
                        if write:
                            reject.detail = {"backfilled": today, "fetch_failed": True}
                            session.add(reject)
                    else:
                        publisher = match_publisher(reject.url, by_host)
                        fetched.append((reject, page, publisher))

                verdicts = {}
                if fetched:
                    try:
                        verdicts = score_batch(
                            [to_input(r, pg, pub) for r, pg, pub in fetched], model
                        )
                    except Exception as e:
                        failed_in_a_row += 1
                        print(
                            f"  batch failed ({failed_in_a_row} in a row), left for "
                            f"the next run: {short_error(e)}"
                        )
                        # The unfetchable rows above are final either way.
                        if write:
                            session.commit()
                        if failed_in_a_row >= MAX_FAILED_BATCHES_IN_A_ROW:
                            print(
                                "The provider looks down. Stopping; run again to resume."
                            )
                            return 1
                        continue
                    failed_in_a_row = 0

                for reject, page, publisher in fetched:
                    verdict = verdicts.get(reject.url)
                    if verdict is None:
                        unanswered += 1
                        print(f"  not answered, left for the next run: {reject.url}")
                        continue
                    reason = sanitize_llm_text(verdict.reason)
                    source = publisher.name if publisher else hostname(reject.url)
                    print(
                        f"  {verdict.score:>3}  {page.title}  [{source}]\n"
                        f"       {reason}"
                    )
                    scored += 1
                    if verdict.score >= SCORE_THRESHOLD:
                        now_passing.append((verdict.score, page.title, reject.url))
                    if write:
                        reject.title = page.title
                        reject.content = page.text[:CONTENT_CAP] or None
                        reject.publisher_id = publisher.id if publisher else None
                        reject.published_at = parse_date(page.published)
                        reject.score = verdict.score
                        reject.reason = reason
                        reject.detail = {"backfilled": today, "model": model}
                        session.add(reject)
                if write:
                    session.commit()
                if fetched:
                    wait_ms(SCORE_BATCH_PAUSE_MS)
        except KeyboardInterrupt:
            session.rollback()
            print(
                "\nInterrupted: the batch in flight was not written. Run again to resume."
            )
            return 130
        finally:
            print(
                f"\nScored {scored}, {unfetched} unfetchable, {unanswered} not answered."
            )
            if now_passing:
                print(
                    f"\n{len(now_passing)} would now pass (score >= {SCORE_THRESHOLD}):"
                )
                for score, title, url in sorted(now_passing, reverse=True):
                    print(f"  {score:>3}  {title}\n       {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
