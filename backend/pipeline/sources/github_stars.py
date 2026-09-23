"""GitHub repos from the public REST API, for the curation agent's ``check_link``.

Stars, forks and the last push are the outside view of a repo: unlike a title
or a README they cannot be written to sound impressive. Not a source any more:
the thin-repo gate that read it at fetch time is gone, and the module kept its
name.

No key needed. Unauthenticated the API allows 60 requests/hour/IP, enough for a
night's handful of lookups; ``GITHUB_TOKEN`` raises the ceiling to 5000.

Every failure returns None, never 0. A rate limit, a timeout or a private repo
must not read as "unpopular".
"""

from __future__ import annotations

import os

from app.platform.logging import log
from pipeline.fetching.http import fetch_with_timeout

GITHUB_API = "https://api.github.com/repos"
LOOKUP_TIMEOUT_SECS = 10.0


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def repo_for(owner: str, repo: str) -> dict[str, object] | None:
    """The repo object the REST API returns, or None when it cannot be read.

    Uncached: the curation agent's ``check_link`` calls this from the long-lived
    API process, where a cached answer would go stale across nights.
    """
    try:
        resp = fetch_with_timeout(
            f"{GITHUB_API}/{owner}/{repo}",
            timeout=LOOKUP_TIMEOUT_SECS,
            headers=_headers(),
        )
    except Exception as e:
        log(f"  GitHub lookup failed for {owner}/{repo}: {e}")
        return None

    if resp.status_code == 404:
        # Renamed, deleted or private. Not a popularity verdict — GitHub is just
        # telling us this URL is not a repo we can read.
        return None
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        log("  GitHub API rate limit hit")
        return None
    if resp.status_code != 200:
        log(f"  GitHub lookup for {owner}/{repo}: HTTP {resp.status_code}")
        return None

    try:
        data = resp.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def has_readme(owner: str, repo: str) -> bool | None:
    """True or False when GitHub says; None when the lookup failed."""
    try:
        resp = fetch_with_timeout(
            f"{GITHUB_API}/{owner}/{repo}/readme",
            timeout=LOOKUP_TIMEOUT_SECS,
            headers=_headers(),
        )
    except Exception:
        return None
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    return None
