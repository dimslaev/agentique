"""Is a URL a lab publishing on its own domain, rather than someone's writeup?

Two callers lean on this and both treat it as a fast path: the scoring rubric
floors a first-party post at 70, and the Hacker News source lets one past its
traction gate.
"""

from __future__ import annotations

from urllib.parse import urlparse

from pipeline.urls import hostname

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
