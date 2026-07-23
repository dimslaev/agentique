"""Every environment variable this pipeline reads, in one place.

Read lazily off ``os.environ`` (never at import) so importing a module to test a
pure function needs no environment and no database. Kept independent of the old
``pipeline.config`` on purpose — this package shares nothing with it.
"""

from __future__ import annotations

import os
from urllib.parse import quote


def postgres_url() -> str:
    server = os.environ["POSTGRES_SERVER"]
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = quote(os.environ["POSTGRES_USER"], safe="")
    password = quote(os.environ.get("POSTGRES_PASSWORD", ""), safe="")
    db = os.environ.get("POSTGRES_DB", "")
    return f"postgresql+psycopg://{user}:{password}@{server}:{port}/{db}"


def residential_proxy_url() -> str | None:
    """Proxy for feed/article fetches that get blocked direct (403/429/paywall).

    Metered, so it is only ever reached for after a direct attempt has already
    failed. ``None`` disables every proxy fallback in the package.
    """
    return os.environ.get("RESIDENTIAL_PROXY_URL") or None


def keep_drop_threshold() -> float:
    """Auto-drop cutoff for the keep/drop pre-filter; 0 disables it.

    Deliberately low (high recall): only the most obvious junk is dropped
    without an LLM call. Read fresh each call so it can be tuned without a
    restart.
    """
    return float(os.environ.get("KEEP_DROP_PREFILTER_THRESHOLD", "0.15"))


def dedup_dist_threshold() -> float:
    """Cosine-distance cutoff for the dedup embedding shortlist. Same-story
    pairs sit around 0.29-0.35 empirically; kept generous above that to favor
    recall since the LLM still makes the final call."""
    return float(os.environ.get("DEDUP_DIST_THRESHOLD", "0.45"))


def dedup_topk() -> int:
    """Max shortlisted existing-article candidates per new article."""
    return int(os.environ.get("DEDUP_TOPK", "5"))
