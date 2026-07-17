"""Primary-link selection for AI News recaps: given every link in a story's
HTML, pick the one that is the actual subject (repo/paper/model/post), not a
share button or a link to the aggregator itself.
"""

from __future__ import annotations

from pipeline.sources.ainews import _pick_primary


def _link(url: str, host: str, text: str = "") -> dict:
    return {"url": url, "host": host, "text": text}


def test_picks_the_only_clean_link():
    links = [_link("https://example.dev/post", "example.dev")]
    assert _pick_primary(links) == {"url": "https://example.dev/post", "kind": "blog"}


def test_a_host_matching_no_known_kind_still_falls_back_to_it_as_other():
    links = [_link("https://example.com/post", "example.com")]
    assert _pick_primary(links) == {"url": "https://example.com/post", "kind": "other"}


def test_prefers_github_over_lower_priority_kinds():
    links = [
        _link("https://openai.com/blog/x", "openai.com"),
        _link("https://github.com/foo/bar", "github.com"),
    ]
    assert _pick_primary(links) == {
        "url": "https://github.com/foo/bar",
        "kind": "github",
    }


def test_priority_order_github_huggingface_arxiv_blog_reddit_tweet():
    links = [
        _link("https://x.com/a", "x.com"),
        _link("https://reddit.com/r/x", "reddit.com"),
        _link("https://arxiv.org/abs/1", "arxiv.org"),
        _link("https://huggingface.co/m", "huggingface.co"),
    ]
    assert _pick_primary(links)["kind"] == "huggingface"


def test_junk_hosts_are_excluded_even_if_nothing_else_is_available():
    links = [_link("https://news.smol.ai/x", "news.smol.ai")]
    assert _pick_primary(links) == {"url": "", "kind": "other"}


def test_twitter_list_links_are_junk_regardless_of_host():
    links = [_link("https://twitter.com/i/lists/123", "twitter.com")]
    assert _pick_primary(links) == {"url": "", "kind": "other"}


def test_empty_url_link_is_junk():
    links = [_link("", "example.com")]
    assert _pick_primary(links) == {"url": "", "kind": "other"}


def test_no_links_at_all_returns_empty():
    assert _pick_primary([]) == {"url": "", "kind": "other"}


def test_unrecognised_host_falls_back_to_first_clean_link_as_other():
    links = [
        _link("https://news.smol.ai/junk", "news.smol.ai"),  # excluded
        _link("https://example-other-host.zzz/post", "example-other-host.zzz"),
    ]
    assert _pick_primary(links) == {
        "url": "https://example-other-host.zzz/post",
        "kind": "other",
    }


def test_known_ai_lab_blog_host_is_classified_as_blog():
    links = [_link("https://www.anthropic.com/news/x", "anthropic.com")]
    assert _pick_primary(links)["kind"] == "blog"
