"""Reading github.com URLs: which of them name a repository, and whose it is.

Every shape a repo link lands in starts ``/owner/repo`` — the root, a PR, an
issue, a blob, a tree path — so one parse serves them all. The owner lists are
this module's own knowledge and are asked about through ``is_known_owner``
rather than exported for callers to match against themselves.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from pipeline.urls import hostname

# Owners whose repos are infrastructure by definition — a release branch or a
# PR under one of these is worth reading on day one, before it has stars of its
# own. Skips the star lookup in ``steps.filter.filter_thin_repos``.
KNOWN_REPO_OWNERS = frozenset(
    {
        "openai",
        "anthropics",
        "anthropic-experimental",
        "google",
        "google-deepmind",
        "google-research",
        "googleapis",
        "meta-llama",
        "facebookresearch",
        "pytorch",
        "tensorflow",
        "huggingface",
        "ggml-org",
        "ggerganov",
        "vllm-project",
        "sgl-project",
        "deepseek-ai",
        "qwenlm",
        "moonshotai",
        "mistralai",
        "nvidia",
        "microsoft",
        "modelcontextprotocol",
        "ollama",
        "langchain-ai",
        "run-llama",
        "unslothai",
        "triton-lang",
        "openvinotoolkit",
        "mlx-explore",
        "apple",
        "allenai",
        "eleutherai",
        "bytedance",
        "tencent",
        "zai-org",
        "baai-agents",
    }
)

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


def is_known_owner(owner: str) -> bool:
    """True for an owner whose repos are infrastructure by definition.

    The star gate in ``steps.filter.filter_thin_repos`` skips the lookup for
    these: a PR against llama.cpp is worth reading on its own merits, and it
    would clear the threshold anyway.
    """
    return owner.lower() in KNOWN_REPO_OWNERS
