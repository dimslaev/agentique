"""Crediting a URL to the publisher whose site it is on."""

from __future__ import annotations

import pytest

from app.core.db.publisher import LinkPlatform, Publisher, PublisherKind
from app.features.collect.publishers import (
    host_kind,
    hosts_to_publishers,
    is_shared_host,
    match_publisher,
    owner_key,
)


def _pub(id_: int, **links: str) -> Publisher:
    return Publisher(
        id=id_,
        slug=f"p{id_}",
        name=f"P{id_}",
        kind=PublisherKind.media,
        links={LinkPlatform(k): v for k, v in links.items()},
    )


def _credited(url: str, *publishers: Publisher) -> int | None:
    match = match_publisher(url, hosts_to_publishers(publishers))
    return match.id if match else None


def test_credits_a_url_to_the_publisher_whose_site_it_is_on() -> None:
    simon = _pub(1, website="https://simonwillison.net")
    assert _credited("https://simonwillison.net/2026/Aug/8/auto-mode/", simon) == 1


def test_a_feed_link_names_the_host_too() -> None:
    hamel = _pub(2, rss="https://hamelhusain.substack.com/feed")
    assert _credited("https://hamelhusain.substack.com/p/evals", hamel) == 2


def test_climbs_to_the_parent_domain() -> None:
    cloudflare = _pub(3, website="https://www.cloudflare.com")
    assert _credited("https://blog.cloudflare.com/ai-code-review/", cloudflare) == 3


def test_a_search_link_is_a_bare_host() -> None:
    anthropic = _pub(4, search="anthropic.com")
    assert _credited("https://www.anthropic.com/news/claude-opus-5", anthropic) == 4


def test_a_shared_platform_host_credits_nobody() -> None:
    """A publisher whose site is a GitHub or Hugging Face page must not claim
    every repo or model card on the platform."""
    hf_blog = _pub(5, website="https://huggingface.co/blog")
    assert _credited("https://huggingface.co/Qwen/Qwen3.8-27B-FP8", hf_blog) is None


def test_a_host_two_publishers_claim_credits_neither() -> None:
    a = _pub(6, website="https://example.com")
    b = _pub(7, rss="https://example.com/feed")
    assert _credited("https://example.com/post", a, b) is None


def test_an_unknown_host_credits_nobody() -> None:
    assert (
        _credited("https://nobody-we-know.dev/post", _pub(8, website="https://a.dev"))
        is None
    )


def test_a_platform_owner_is_credited_by_path() -> None:
    anthropic = _pub(
        9, website="https://anthropic.com", github="https://github.com/anthropics"
    )
    assert _credited("https://github.com/anthropics/claude-code/pull/1", anthropic) == 9
    assert _credited("https://github.com/someone-else/repo", anthropic) is None


def test_a_hugging_face_blog_feed_claims_the_blog_not_the_models() -> None:
    hf = _pub(10, rss="https://huggingface.co/blog/feed.xml")
    assert _credited("https://huggingface.co/blog/smolagents", hf) == 10
    assert _credited("https://huggingface.co/Qwen/Qwen3", hf) is None


@pytest.mark.parametrize(
    "url, key",
    [
        ("https://github.com/MattPocock/skills", "github.com/mattpocock"),
        ("https://github.com/features/copilot", None),
        ("https://huggingface.co/datasets/allenai/tulu", "huggingface.co/allenai"),
        ("https://hf.co/Qwen/Qwen3", "huggingface.co/qwen"),
        ("https://huggingface.co/papers/2609.1", None),
        ("https://medium.com/feed/airbnb-engineering", "medium.com/airbnb-engineering"),
        ("https://medium.com/@someone/a-post-123", "medium.com/@someone"),
        ("https://medium.com/tag/ai", None),
        ("https://simonwillison.net/2026/", None),
    ],
)
def test_owner_key(url: str, key: str | None) -> None:
    assert owner_key(url) == key


def test_a_personal_host_is_an_individual() -> None:
    assert host_kind("someone.github.io") == PublisherKind.individual
    assert host_kind("goodfire.ai") == PublisherKind.unknown


@pytest.mark.parametrize(
    "host, shared",
    [
        ("reddit.com", True),
        ("old.reddit.com", True),
        ("m.youtube.com", True),
        ("youtu.be", True),
        ("mobile.twitter.com", True),
        ("gist.github.com", True),
        # A subdomain of these is one writer's site.
        ("writer.substack.com", False),
        ("someone.medium.com", False),
        ("notreddit.com", False),
        ("simonwillison.net", False),
    ],
)
def test_a_shared_platform_includes_its_subdomains(host: str, shared: bool) -> None:
    assert is_shared_host(host) is shared


def test_a_publisher_on_a_platform_subdomain_claims_nothing() -> None:
    sub = _pub(11, website="https://old.reddit.com/r/LocalLLaMA")
    assert _credited("https://old.reddit.com/r/LocalLLaMA/comments/x", sub) is None


def test_a_substack_writer_still_claims_their_own_subdomain() -> None:
    writer = _pub(12, substack="https://writer.substack.com")
    assert _credited("https://writer.substack.com/p/a-post", writer) == 12
