"""The article as it changes shape on its way down the funnel.

One type per stage, each fully populated by the step that produces it:

    RawItem    what a source emits -- title, url, content, date, source
    Candidate  + the publisher it belongs to   (fetch.resolve_publishers)
    Scored     + the curation agent's score    (curation.approve)
    Summarized + the summary a reader sees      (curation.approve)
    Persisted  + the id of the row it landed in (persist.insert_articles)

Each stage subclasses the one before, so a step that only needs a ``Candidate``
also accepts a ``Scored`` or a ``Persisted``, while a step that needs a score
cannot be handed something that has not been judged. The signatures
are the funnel: reading them tells you the order without opening ``run.py``.

This replaced a single ``FetchedArticle`` where every key was optional at every
stage. That shape could not say which step filled what, so each step's contract
lived in a docstring and a mis-ordered call failed at runtime with a KeyError
instead of at the call site.

``curation.approve`` reshapes a ``Persisted`` into the narrower
``ProcessedArticle`` that ``embed_articles`` consumes.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict

from app.catalog.models import Category


class RawItem(TypedDict):
    """One item as a source adapter emits it, before anything is known about it.

    ``content`` may be empty at this point: the thin sources (Hacker News,
    Lab Watch, Newsletter) arrive with a blurb or nothing at all, and
    ``fetch._with_content`` fills it before the item goes any further.
    """

    title: str
    url: str
    content: str
    published_date: str | None
    source: str
    # Only the aggregator sources that carry a public reception signal (Hacker
    # News points/comments) have one. Shown to the agent as evidence, not
    # merely used as a gate -- see sources/hn.py.
    traction: NotRequired[str]
    # The repo / model / paper / docs links the article body makes, grouped by
    # ``fetching.page_facts``. Absent when the text came from nowhere with HTML.
    links: NotRequired[dict[str, list[str]]]


class Candidate(RawItem):
    """An item resolved to the Publisher it came from, and so worth spending on.

    Everything downstream of ``resolve_publishers`` reads ``trust`` (it goes to
    the scoring prompt) and ``topic_gated`` (the title gate), so both are
    required here rather than looked up defensively at each use.
    """

    publisher_id: int
    trust: str
    # PublisherKind value; with trust it decides the scoring threshold.
    publisher_kind: str
    topic_gated: bool


class Scored(Candidate):
    """A candidate the curation agent approved, with the score it gave."""

    score: int
    # The agent's one-sentence account of the score.
    score_reason: str | None


class Summarized(Scored):
    """A scored article with the summary the agent wrote. Nothing is inserted
    without one."""

    summary: str


class Persisted(Summarized):
    """A scored article that is now a row: ``id`` is the Article's primary key.

    ``title`` and ``content`` are the sanitized values actually stored, not the
    raw ones the source emitted.
    """

    id: int


class ProcessedArticle(TypedDict):
    """What enrichment hands the embedder: a stored article reduced to the
    fields the embedding text is built from."""

    id: int
    url: str
    title: str
    score: int
    snippet: str
    categories: list[Category]
