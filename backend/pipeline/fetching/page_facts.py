"""What a page points at: the repos, models, papers and first-party docs it links.

The curation agent judges an article partly by what it rests on — a release
post with a repo and weights behind it is a different thing from one with a
waitlist. Those links are in the HTML the extractor already fetched, so they
are read there once, grouped, and stored beside the text, instead of the agent
fetching the page again to find them.

Only links inside the article body count: trafilatura drops the nav, footer and
sidebar before the links are read, so a "Star us on GitHub" in a site footer
does not turn every post on that site into a repo announcement.
"""

from __future__ import annotations

import html as html_lib
import re
from urllib.parse import urljoin, urlparse, urlunparse

import trafilatura

from pipeline.first_party import is_first_party
from pipeline.github import github_repo_from_url
from pipeline.urls import hostname

# What one group holds at most. A survey post can link fifty papers; the agent
# needs to see what an article rests on, not its bibliography.
MAX_LINKS_PER_GROUP = 10

PAPER_HOSTS = frozenset({"arxiv.org", "openreview.net", "doi.org", "dx.doi.org"})
HF_HOSTS = frozenset({"huggingface.co", "hf.co"})
# First path segments on huggingface.co that are site pages, not a model.
HF_SITE_PAGES = frozenset(
    {
        "blog",
        "docs",
        "learn",
        "join",
        "login",
        "pricing",
        "models",
        "settings",
        "organizations",
        "collections",
        "tasks",
        "enterprise",
        "posts",
        "chat",
    }
)
GITLAB_SITE_PAGES = frozenset({"explore", "users", "help", "dashboard", "groups"})

_REF_TARGET = re.compile(r'<ref target="([^"]+)"')


def _clean(url: str, page_url: str) -> str | None:
    """Absolute http(s) URL with the fragment dropped, or None."""
    absolute = urljoin(page_url, url.strip())
    parts = urlparse(absolute)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return urlunparse(parts._replace(fragment=""))


def _same_site(a: str, b: str) -> bool:
    """True when two hosts share their last two labels (blog.x.com, docs.x.com)."""
    return bool(a and b) and a.split(".")[-2:] == b.split(".")[-2:]


def _classify(url: str, page_host: str) -> tuple[str, str] | None:
    """(group, normalized url) for one link, or None when it is in no group."""
    host = hostname(url)
    path = [p for p in urlparse(url).path.split("/") if p]

    if host == "github.com":
        repo = github_repo_from_url(url)
        return ("repo", f"https://github.com/{repo[0]}/{repo[1]}") if repo else None
    if host == "gitlab.com":
        if len(path) >= 2 and path[0].lower() not in GITLAB_SITE_PAGES:
            return "repo", f"https://gitlab.com/{path[0]}/{path[1]}"
        return None
    if host in HF_HOSTS:
        if path[:1] == ["papers"]:
            return "paper", url
        if path[:1] in (["datasets"], ["spaces"]) and len(path) >= 3:
            return "model", f"https://huggingface.co/{'/'.join(path[:3])}"
        if len(path) >= 2 and path[0].lower() not in HF_SITE_PAGES:
            return "model", f"https://huggingface.co/{path[0]}/{path[1]}"
        return ("docs", url) if is_first_party(url) else None
    if host in PAPER_HOSTS:
        return "paper", url
    if is_first_party(url) or _same_site(host, page_host):
        return "docs", url
    return None


def group_links(urls: list[str], page_url: str) -> dict[str, list[str]]:
    """Sort a page's links into repo / model / paper / docs. Pure.

    Deduped after normalizing (every blob of one repo is the repo), in the
    order the page links them, at most ``MAX_LINKS_PER_GROUP`` each. Groups
    with nothing in them are left out, and a link back to the page itself is
    not a link.
    """
    page_host = hostname(page_url)
    page = _clean(page_url, page_url)
    groups: dict[str, list[str]] = {}
    for raw in urls:
        url = _clean(raw, page_url)
        if url is None or url == page:
            continue
        hit = _classify(url, page_host)
        if hit is None:
            continue
        group, normalized = hit
        bucket = groups.setdefault(group, [])
        if normalized not in bucket and len(bucket) < MAX_LINKS_PER_GROUP:
            bucket.append(normalized)
    return groups


def outbound_links(html: str, page_url: str) -> dict[str, list[str]]:
    """The grouped links in an HTML page's article body; {} when there are none."""
    if not html:
        return {}
    xml = trafilatura.extract(
        html,
        url=page_url,
        include_links=True,
        include_tables=True,
        include_comments=False,
        output_format="xml",
    )
    if not xml:
        return {}
    targets = [html_lib.unescape(t) for t in _REF_TARGET.findall(xml)]
    return group_links(targets, page_url)
