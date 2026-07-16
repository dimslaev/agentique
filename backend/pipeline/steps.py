from __future__ import annotations

import re

from app.models_agentique import ArticleKind

SCORE_THRESHOLD = 76
PROMPT_CONTENT_CAP = 1500

# Below this, content is a teaser/blurb rather than an article, and the
# summarizer fails on it ~30-40% of the time (vs ~2% above it). Used to decide
# whether a fetched item still needs a network re-fetch of its full text.
MIN_CONTENT_CHARS = 500

NON_REPO_OWNERS = {
    "features",
    "login",
    "pricing",
    "about",
    "marketplace",
    "explore",
    "topics",
    "collections",
    "trending",
    "sponsors",
    "orgs",
    "apps",
    "contact",
    "security",
}

GITHUB_REPO_RE = re.compile(
    r"https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"
)


def github_repo_from_content(content: str) -> str | None:
    match = GITHUB_REPO_RE.search(content)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    if owner.lower() in NON_REPO_OWNERS:
        return None
    return f"https://github.com/{owner}/{repo}"


def kind_from_url(url: str) -> ArticleKind | None:
    """Deterministic ArticleKind from a URL host, or None if inconclusive."""
    try:
        from urllib.parse import urlparse

        host = urlparse(url).hostname or ""
        host = host.removeprefix("www.")
        if host in ("github.com", "gitlab.com"):
            return ArticleKind.repo
        if host in ("huggingface.co", "hf.co"):
            return ArticleKind.model
        if host in ("arxiv.org", "ar5iv.labs.arxiv.org"):
            return ArticleKind.paper
    except Exception:
        pass
    return None


# TRUST_BY_SOURCE removed under the new schema: per-article trust now comes from
# Publisher.trust (resolved via pipeline.publishers), not a hard-coded map.
