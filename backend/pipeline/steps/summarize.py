"""Step 4: summarize what passed scoring, before it is inserted.

The summary is what a reader sees under the title, so an article the model
cannot summarize is dropped here rather than inserted bare. Content is already
at least ``fetch.MIN_SUMMARIZABLE_CHARS`` by now, so a drop means the call
failed or the answer was garbage.

An unusable summary is recorded in ScoredUrl, like a sub-threshold score, so
the article is not fetched, scored and summarized again every run. A failed
call is not: a provider outage must not become a permanent reject, so the next
run fetches and scores those again.
"""

from __future__ import annotations

from sqlmodel import Session

from app.platform.logging import log, short_error, wait_ms
from baml_client.sync_client import b
from pipeline.llm_text import is_corrupted, sanitize_llm_text
from pipeline.models import ScoredUrl
from pipeline.types import Scored, Summarized

# The article text sent to the model. Long enough to summarize a full post
# without blowing up the prompt; most articles are well under this.
MAX_CONTENT_CHARS = 12000

# Bullet count scales with article length (a hook line and an optional "Catch:"
# line sit on top of this). Word-count breakpoints, upper end exclusive.
LENGTH_BANDS = [(400, 3), (1000, 4), (2000, 6), (4000, 7)]
MAX_BULLETS = 8

# One call per article, not batched, so a failed call costs one article. The
# pause keeps a run under NIM's concurrency cap.
CALL_PAUSE_MS = 1000


def bullet_count(word_count: int) -> int:
    for max_words, bullets in LENGTH_BANDS:
        if word_count < max_words:
            return bullets
    return MAX_BULLETS


def accept_summary(raw: str) -> str | None:
    """The summary to store, or None if the model's answer is unusable. Pure."""
    lines = (sanitize_llm_text(line) for line in raw.splitlines())
    summary = "\n".join(line for line in lines if line)
    if not summary or is_corrupted(summary):
        return None
    return summary


def summarize(title: str, content: str) -> str | None:
    """One article's summary, or None if the answer is unusable. Raises if the
    call itself fails."""
    text = content[:MAX_CONTENT_CHARS]
    raw = b.SummarizeArticle(title, text, bullet_count(len(text.split())))
    return accept_summary(raw)


def summarize_articles(session: Session, articles: list[Scored]) -> list[Summarized]:
    if not articles:
        return []

    log(f"  Summarizing {len(articles)} articles...")
    summarized: list[Summarized] = []
    unusable = 0
    failed = 0
    last_error: Exception | None = None
    for i, a in enumerate(articles):
        try:
            summary = summarize(a["title"], a["content"])
        except Exception as e:
            failed += 1
            last_error = e
            log(f"    Summary failed, not inserting {a['url']}: {short_error(e)}")
        else:
            if summary:
                summarized.append({**a, "summary": summary})
            else:
                session.merge(ScoredUrl(url=a["url"]))
                unusable += 1
                log(f"    Unusable summary, not inserting {a['url']}")
        if i + 1 < len(articles):
            wait_ms(CALL_PAUSE_MS)

    if unusable:
        session.commit()

    # Every call failing is the provider being down, not a bad article. Let it
    # out so the source records the error and the run report shows it.
    if last_error is not None and failed == len(articles):
        raise last_error

    log(f"  {len(summarized)}/{len(articles)} articles summarized")
    return summarized
