"""The pipeline's steps, in the order run.py applies them.

    fetch      - poll each source, fill content, stamp publisher/trust per item
    filter     - drop known URLs, dead domains, semantic duplicates
    categorize - two cheap static gates, then the LLM category matcher
    persist    - insert what matched, with its categories
    enrich     - titles, summary/kind, embedding

Every step takes the session and a list of articles and returns the survivors,
so run.py reads as the funnel it is. Steps own their own logging and commits.
"""

from __future__ import annotations

from baml_client.types import ArticleInput
from pipeline.types import FetchedArticle

# Enough of the article for the LLM to judge it by; the full text would blow up
# the prompt for no gain in the scoring/dedup/title calls.
SNIPPET_CAP = 200


def to_baml_input(a: FetchedArticle) -> ArticleInput:
    """Build a BAML ArticleInput from a fetched-article dict.

    ``trust`` is stamped by the fetch step from Publisher.trust.
    """
    content = a.get("content") or ""
    return ArticleInput(
        url=a["url"],
        title=a["title"],
        source=a["source"],
        snippet=content[:SNIPPET_CAP] if content else None,
        trust=a.get("trust"),
    )
