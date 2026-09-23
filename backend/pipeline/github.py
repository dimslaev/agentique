"""Reading github.com URLs: which of them name a repository, and whose it is.

Every shape a repo link lands in starts ``/owner/repo`` — the root, a PR, an
issue, a blob, a tree path — so one parse serves them all.
"""

from __future__ import annotations

from urllib.parse import urlparse

from pipeline.urls import hostname

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
