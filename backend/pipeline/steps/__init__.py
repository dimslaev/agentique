"""The pipeline's steps, in the order run.py applies them.

    fetch    - poll each source, fill content, stamp publisher/trust per item
    filter   - drop known URLs, dead domains, semantic duplicates
    score    - cheap keep/drop pre-filter, then the LLM scorer
    persist  - insert what passed
    enrich   - titles, categories/kind/tags, embedding

Every step takes the session and a list of articles and returns the survivors,
so run.py reads as the funnel it is. Steps own their own logging and commits.

The article changes type as it goes -- RawItem -> Candidate -> Scored ->
Persisted, see pipeline.types -- so a step's signature says where in the funnel
it belongs.
"""

from __future__ import annotations

from baml_client.types import ArticleInput
from pipeline.types import Candidate

# Enough of the article for the LLM to judge it by; the full text would blow up
# the prompt for no gain in the scoring/dedup/title calls.
SNIPPET_CAP = 200


def to_baml_input(a: Candidate) -> ArticleInput:
    """Build a BAML ArticleInput from a candidate.

    Takes a ``Candidate`` rather than a ``RawItem`` because ``trust`` is part
    of what the model is asked to weigh, and that is only known once the
    publisher is resolved. ``traction`` stays optional: only the aggregator
    sources have one to report.
    """
    content = a["content"]
    return ArticleInput(
        url=a["url"],
        title=a["title"],
        source=a["source"],
        snippet=content[:SNIPPET_CAP] if content else None,
        trust=a["trust"],
        traction=a.get("traction"),
    )
