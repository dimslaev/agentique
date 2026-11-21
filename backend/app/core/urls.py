"""URL normalisation: feed endpoints, comparable hostnames, and first-party lab
domains."""

from __future__ import annotations

from urllib.parse import urlparse


def feed_url(url: str, is_substack: bool = False) -> str:
    """Normalise a publisher link to the feed endpoint to actually poll.

    A bare Substack link (``https://foo.substack.com``, or a custom domain
    stored under the ``substack`` platform) serves the HTML site, not the feed -
    feedparser finds no entries and the source silently yields nothing. Substack
    always serves the feed at ``/feed``. Pass ``is_substack`` when the link's
    platform says so; the host check catches bare substack.com links stored
    under ``rss``. Idempotent, so it is safe to apply more than once.
    """
    trimmed = url.rstrip("/")
    if (is_substack or trimmed.endswith(".substack.com")) and not trimmed.endswith(
        "/feed"
    ):
        return f"{trimmed}/feed"
    return url


def hostname(url: str) -> str:
    """Lowercase host without a ``www.`` prefix, or "" if the URL has no host."""
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return ""
    return host.lower().removeprefix("www.")


# Domains where a post is the release itself rather than someone's writeup of
# it. Two places lean on this: the scoring rubric floors these at 70, and the
# Hacker News source lets them past its traction gate — a lab's own announcement
# is real news at zero upvotes, and waiting for the votes would mean publishing
# it a day late, which is the whole reason the "new" firehose is polled.
FIRST_PARTY_HOSTS = frozenset(
    {
        "openai.com",
        "anthropic.com",
        "claude.com",
        "deepmind.google",
        "blog.google",
        "ai.meta.com",
        "ai.google.dev",
        "mistral.ai",
        "qwen.ai",
        "kimi.com",
        "moonshot.ai",
        "deepseek.com",
        "x.ai",
        "cohere.com",
        "ai21.com",
        "stability.ai",
        "allenai.org",
        "nvidia.com",
        "blogs.nvidia.com",
        "developer.nvidia.com",
        "research.google",
        "microsoft.com",
        "z.ai",
    }
)


def is_first_party(url: str) -> bool:
    """True when the URL is a lab publishing on its own domain.

    Matches subdomains too (``platform.claude.com``, ``blog.mistral.ai``), so a
    lab moving its newsroom to a subdomain does not silently drop out of the
    fast path. ``huggingface.co`` is deliberately absent as a bare host - it is
    mostly user-uploaded - so only its editorial blog qualifies.
    """
    host = hostname(url)
    if not host:
        return False
    if host in ("huggingface.co", "hf.co"):
        return urlparse(url).path.startswith("/blog")
    return any(host == h or host.endswith(f".{h}") for h in FIRST_PARTY_HOSTS)


# Hosts many unrelated authors publish under: the host alone says nothing about
# who wrote it, so no publisher is credited from it. On the ones in
# collect's OWNER_HOSTS the first path segment does name the author.
# huggingface.co is here because "Hugging Face Blog" would otherwise claim
# every model card.
SHARED_HOSTS = frozenset(
    {
        "github.com",
        "huggingface.co",
        "linkedin.com",
        "medium.com",
        "reddit.com",
        "substack.com",
        "twitter.com",
        "x.com",
        "youtu.be",
        "youtube.com",
    }
)
# Shared hosts whose subdomains are one author's site (writer.substack.com).
# Any other shared host's subdomain is the platform itself (old.reddit.com,
# m.youtube.com), unless a publisher's own link names it
# (engineering.linkedin.com, see `hosts_to_publishers`).
PERSONAL_SUBDOMAIN_HOSTS = frozenset({"medium.com", "substack.com"})


def is_shared_host(host: str) -> bool:
    """A host many unrelated authors publish under. Pure."""
    return any(
        host == shared
        or (host.endswith(f".{shared}") and shared not in PERSONAL_SUBDOMAIN_HOSTS)
        for shared in SHARED_HOSTS
    )
