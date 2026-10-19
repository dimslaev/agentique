"""GitHub: which github.com URLs name a repository, and what the REST API says
about a repo or an account.

Every shape a repo link lands in starts ``/owner/repo`` — the root, a PR, an
issue, a blob, a tree path — so one parse serves them all.

The API needs no key. Unauthenticated it allows 60 requests/hour/IP, enough for
a night's handful of lookups; ``GITHUB_TOKEN`` raises the ceiling to 5000.
Every failed lookup returns None, never 0: a rate limit, a timeout or a private
repo must not read as "unpopular".
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from app.core.http import fetch_with_timeout
from app.core.logging import log
from app.core.urls import hostname

GITHUB_API = "https://api.github.com/repos"
LOOKUP_TIMEOUT_SECS = 10.0

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


def github_repo_from_url(url: str) -> tuple[str, str] | None:
    """``(owner, repo)`` for a github.com URL that names a repository, else None.

    Handles every shape a link lands in — the repo root, a PR, an issue, a blob
    or a tree path — because they all start ``/owner/repo``. Anything else on
    the host (a user profile, ``/features``, gist.github.com) is not a repo and
    returns None rather than a bogus pair.
    """
    if hostname(url) != "github.com":
        return None
    parts = [p for p in urlparse(url).path.split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1]
    if owner.lower() in NON_REPO_OWNERS:
        return None
    return owner, repo.removesuffix(".git")


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


def account_type(owner: str) -> str | None:
    """``"User"`` or ``"Organization"`` for a GitHub account, None when the
    lookup failed."""
    try:
        resp = fetch_with_timeout(
            f"https://api.github.com/users/{owner}",
            timeout=LOOKUP_TIMEOUT_SECS,
            headers=_headers(),
        )
    except Exception as e:
        log(f"  GitHub lookup failed for {owner}: {e}")
        return None
    if resp.status_code != 200:
        log(f"  GitHub lookup for {owner}: HTTP {resp.status_code}")
        return None
    try:
        kind = resp.json().get("type")
    except Exception:
        return None
    return kind if isinstance(kind, str) else None
