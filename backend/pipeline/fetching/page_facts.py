"""``check_link``: look a repo or model up where it lives.

The facts a page cannot fake: stars, downloads, the last push, whether there
are weights at all. The curation agent judges an article partly by what it
rests on — a release post with a repo and weights behind it is a different
thing from one with a waitlist. The links themselves are read once at fetch
time, beside the text (``app.core.extract.outbound_links``).
"""

from __future__ import annotations

from urllib.parse import quote, urlparse

from app.core.extract import GITLAB_SITE_PAGES, HF_HOSTS, HF_SITE_PAGES
from app.core.github import github_repo_from_url, has_readme, repo_for
from app.core.http import fetch_with_timeout
from app.core.urls import hostname

# What any lookup that did not answer reads as. Never 0 or False: a rate limit
# must not look like a repo nobody starred or a model with no weights.
UNKNOWN = "unknown"
LOOKUP_TIMEOUT_SECS = 10.0
GITLAB_API = "https://gitlab.com/api/v4/projects"
HF_API = "https://huggingface.co/api"
WEIGHT_SUFFIXES = (
    ".safetensors",
    ".bin",
    ".gguf",
    ".pt",
    ".pth",
    ".ckpt",
    ".onnx",
    ".h5",
    ".msgpack",
)

type Facts = dict[str, object]


class LinkError(Exception):
    """A URL ``check_link`` does not read. The message names the tool that does."""


def _or_unknown(value: object) -> object:
    return UNKNOWN if value is None or value == "" else value


def _get_json(url: str) -> dict[str, object] | None:
    try:
        resp = fetch_with_timeout(url, timeout=LOOKUP_TIMEOUT_SECS)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _nested(data: dict[str, object], *keys: str) -> object:
    """``data[k1][k2]...``, or None wherever a level is missing."""
    value: object = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def github_facts(owner: str, repo: str, data: dict[str, object] | None) -> Facts:
    """What the GitHub repo object says, in check_link's shape. Pure."""
    facts: Facts = {"url": f"https://github.com/{owner}/{repo}", "kind": "repo"}
    if data is None:
        return {**facts, "lookup": UNKNOWN}
    return {
        **facts,
        "description": _or_unknown(data.get("description")),
        "stars": _or_unknown(data.get("stargazers_count")),
        "forks": _or_unknown(data.get("forks_count")),
        "last_push": _or_unknown(data.get("pushed_at")),
        "license": _or_unknown(_nested(data, "license", "spdx_id")),
        "archived": _or_unknown(data.get("archived")),
    }


def gitlab_facts(path: str, data: dict[str, object] | None) -> Facts:
    """What the GitLab project object says, in check_link's shape. Pure."""
    facts: Facts = {"url": f"https://gitlab.com/{path}", "kind": "repo"}
    if data is None:
        return {**facts, "lookup": UNKNOWN}
    readme = data.get("readme_url")
    return {
        **facts,
        "description": _or_unknown(data.get("description")),
        "stars": _or_unknown(data.get("star_count")),
        "forks": _or_unknown(data.get("forks_count")),
        "last_push": _or_unknown(data.get("last_activity_at")),
        "license": _or_unknown(_nested(data, "license", "key")),
        "archived": _or_unknown(data.get("archived")),
        "has_readme": UNKNOWN if "readme_url" not in data else readme is not None,
    }


def _hf_license(data: dict[str, object]) -> object:
    card = _nested(data, "cardData", "license")
    if card:
        return card
    tags = data.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.startswith("license:"):
                return tag.removeprefix("license:")
    return None


def huggingface_facts(repo_id: str, kind: str, data: dict[str, object] | None) -> Facts:
    """What the Hugging Face API says about a model or dataset. Pure."""
    prefix = "datasets/" if kind == "dataset" else ""
    facts: Facts = {"url": f"https://huggingface.co/{prefix}{repo_id}", "kind": kind}
    if data is None:
        return {**facts, "lookup": UNKNOWN}
    siblings = data.get("siblings")
    files = (
        [s.get("rfilename", "") for s in siblings if isinstance(s, dict)]
        if isinstance(siblings, list)
        else None
    )
    facts |= {
        "downloads": _or_unknown(data.get("downloads")),
        "likes": _or_unknown(data.get("likes")),
        "last_modified": _or_unknown(data.get("lastModified")),
        "license": _or_unknown(_hf_license(data)),
        "files": UNKNOWN if files is None else len(files),
    }
    if kind == "model":
        facts["weights"] = (
            UNKNOWN
            if files is None
            else any(str(f).endswith(WEIGHT_SUFFIXES) for f in files)
        )
    return facts


def check_link(url: str) -> Facts:
    """Look up the GitHub or GitLab repo, or the Hugging Face model or dataset,
    a URL names.

    Anything else raises ``LinkError``: an arXiv abstract or a docs page is
    small enough to read with ``web_fetch``. A lookup that fails comes back with
    ``lookup: unknown`` and no numbers, and a single missing field reads
    ``unknown`` — never 0.
    """
    host = hostname(url)
    path = [p for p in urlparse(url).path.split("/") if p]

    if host == "github.com":
        repo = github_repo_from_url(url)
        if repo:
            owner, name = repo
            facts = github_facts(owner, name, repo_for(owner, name))
            if "lookup" not in facts:
                readme = has_readme(owner, name)
                facts["has_readme"] = UNKNOWN if readme is None else readme
            return facts
    elif host == "gitlab.com":
        if len(path) >= 2 and path[0].lower() not in GITLAB_SITE_PAGES:
            project = "/".join(path[: path.index("-")] if "-" in path else path)
            data = _get_json(f"{GITLAB_API}/{quote(project, safe='')}?license=true")
            return gitlab_facts(project, data)
    elif host in HF_HOSTS:
        if path[:1] == ["datasets"] and len(path) >= 3:
            repo_id = f"{path[1]}/{path[2]}"
            data = _get_json(f"{HF_API}/datasets/{repo_id}")
            return huggingface_facts(repo_id, "dataset", data)
        if len(path) >= 2 and path[0].lower() not in HF_SITE_PAGES | {
            "spaces",
            "papers",
            "datasets",
        }:
            repo_id = f"{path[0]}/{path[1]}"
            data = _get_json(f"{HF_API}/models/{repo_id}")
            return huggingface_facts(repo_id, "model", data)

    raise LinkError(
        f"check_link reads GitHub and GitLab repos and Hugging Face models and "
        f"datasets; {url} is none of those. Read it with web_fetch."
    )
