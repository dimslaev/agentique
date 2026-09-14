"""Crediting a URL to the publisher whose site it is on."""

from __future__ import annotations

from types import SimpleNamespace

from pipeline.publishers import hosts_to_publishers, match_publisher


def _pub(id_: int, **links: str) -> SimpleNamespace:
    return SimpleNamespace(id=id_, links=links)


def _credited(url: str, *publishers: SimpleNamespace) -> int | None:
    match = match_publisher(url, hosts_to_publishers(publishers))  # type: ignore[arg-type]
    return match.id if match else None


def test_credits_a_url_to_the_publisher_whose_site_it_is_on():
    simon = _pub(1, website="https://simonwillison.net")
    assert _credited("https://simonwillison.net/2026/Aug/8/auto-mode/", simon) == 1


def test_a_feed_link_names_the_host_too():
    hamel = _pub(2, rss="https://hamelhusain.substack.com/feed")
    assert _credited("https://hamelhusain.substack.com/p/evals", hamel) == 2


def test_climbs_to_the_parent_domain():
    cloudflare = _pub(3, website="https://www.cloudflare.com")
    assert _credited("https://blog.cloudflare.com/ai-code-review/", cloudflare) == 3


def test_a_search_link_is_a_bare_host():
    anthropic = _pub(4, search="anthropic.com")
    assert _credited("https://www.anthropic.com/news/claude-opus-5", anthropic) == 4


def test_a_shared_platform_host_credits_nobody():
    """A publisher whose site is a GitHub or Hugging Face page must not claim
    every repo or model card on the platform."""
    hf_blog = _pub(5, website="https://huggingface.co/blog")
    assert _credited("https://huggingface.co/Qwen/Qwen3.8-27B-FP8", hf_blog) is None


def test_a_host_two_publishers_claim_credits_neither():
    a = _pub(6, website="https://example.com")
    b = _pub(7, rss="https://example.com/feed")
    assert _credited("https://example.com/post", a, b) is None


def test_an_unknown_host_credits_nobody():
    assert (
        _credited("https://nobody-we-know.dev/post", _pub(8, website="https://a.dev"))
        is None
    )
