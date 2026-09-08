"""ArticleKind straight from a URL's host, for the hosts where it is settled.

A github.com link is a repo and an arxiv.org link is a paper whatever the LLM
would say about the text, so the host is asked first and the categorizer is
only consulted when it comes back inconclusive.
"""

from __future__ import annotations

from app.catalog.models import ArticleKind
from pipeline.urls import hostname


def kind_from_url(url: str) -> ArticleKind | None:
    """Deterministic ArticleKind from a URL host, or None if inconclusive."""
    host = hostname(url)
    if host in ("github.com", "gitlab.com"):
        return ArticleKind.repo
    if host in ("huggingface.co", "hf.co"):
        return ArticleKind.model
    if host in ("arxiv.org", "ar5iv.labs.arxiv.org"):
        return ArticleKind.paper
    return None
