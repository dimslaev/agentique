"""GitHub repos from the public REST API: star counts, and the repo object.

One repo, one signal: how many people have starred it. That is the cheapest
honest answer to "is this a project anyone uses, or a weekend upload the author
just posted about" — and unlike a title or a README it cannot be written to
sound impressive.

No key needed. Unauthenticated the API allows 60 requests/hour/IP and a run
looks up a handful of repos, so the default path stays keyless; ``GITHUB_TOKEN``
raises the ceiling to 5000 if that ever changes.

Every failure returns None, never 0. A rate limit, a timeout or a private repo
must not read as "unpopular" — callers treat None as "no opinion" and keep the
article.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor

from app.platform.logging import log
from pipeline.fetching.http import fetch_with_timeout

GITHUB_API = "https://api.github.com/repos"
STARS_TIMEOUT_SECS = 10.0
STARS_CONCURRENCY = 8

# One process-wide cache. A repo's star count does not move meaningfully inside
# a single run, and the same repo shows up on more than one source (HN links the
# release, a newsletter links the same repo) — those must not be two API calls against
# a 60/hour budget.
_cache: dict[tuple[str, str], int | None] = {}
_cache_lock = threading.Lock()


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
            timeout=STARS_TIMEOUT_SECS,
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
            timeout=STARS_TIMEOUT_SECS,
            headers=_headers(),
        )
    except Exception:
        return None
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    return None


def _fetch_stars(owner: str, repo: str) -> int | None:
    data = repo_for(owner, repo)
    count = data.get("stargazers_count") if data else None
    return count if isinstance(count, int) else None


def stars_for(repos: list[tuple[str, str]]) -> dict[tuple[str, str], int | None]:
    """Star counts for each ``(owner, repo)``, looked up in parallel.

    A repo already looked up in this process is served from the cache. Missing
    or failed lookups map to None, which callers must read as "unknown", not
    "zero".
    """
    if not repos:
        return {}

    wanted = list(dict.fromkeys(repos))
    with _cache_lock:
        todo = [r for r in wanted if r not in _cache]

    if todo:
        with ThreadPoolExecutor(max_workers=STARS_CONCURRENCY) as executor:
            fetched = list(executor.map(lambda r: _fetch_stars(*r), todo))
        with _cache_lock:
            _cache.update(dict(zip(todo, fetched, strict=True)))

    with _cache_lock:
        return {r: _cache.get(r) for r in wanted}
