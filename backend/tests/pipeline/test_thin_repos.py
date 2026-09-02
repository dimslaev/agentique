"""The GitHub repo gate: which URLs it recognises as repos, and what it does
with the star count it gets back.

The star lookup itself is stubbed — these pin the decisions around it, above
all the two that must never regress: a failed lookup keeps the article, and a
known owner never costs a request.
"""

from __future__ import annotations

import pytest

from pipeline.heuristics import github_repo_from_url
from pipeline.steps import filter as filter_step
from pipeline.types import FetchedArticle


class _FakeSession:
    """Just enough Session for the filter: it records what it would record."""

    def __init__(self) -> None:
        self.merged: list[str] = []
        self.commits = 0

    def merge(self, obj) -> None:
        self.merged.append(obj.url)

    def commit(self) -> None:
        self.commits += 1


def _article(url: str) -> FetchedArticle:
    return {
        "title": "An LLM thing",
        "url": url,
        "content": "",
        "published_date": None,
        "source": "Hacker News",
    }


def _run(monkeypatch, articles, stars, min_stars=50):
    """Run the filter with a canned star table, returning (kept, looked_up)."""
    looked_up: list[tuple[str, str]] = []

    def stars_for(repos):
        looked_up.extend(repos)
        return {r: stars.get(r) for r in repos}

    monkeypatch.setattr(filter_step, "stars_for", stars_for)
    monkeypatch.setattr(filter_step, "github_min_stars", lambda: min_stars)
    session = _FakeSession()
    kept = filter_step.filter_thin_repos(session, articles, "Hacker News")
    return kept, looked_up, session


# ─── github_repo_from_url ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://github.com/ggml-org/llama.cpp", ("ggml-org", "llama.cpp")),
        ("https://www.github.com/ggml-org/llama.cpp", ("ggml-org", "llama.cpp")),
        # every shape a repo link lands in starts /owner/repo
        ("https://github.com/ggml-org/llama.cpp/pull/24219", ("ggml-org", "llama.cpp")),
        ("https://github.com/openai/codex/issues/30364", ("openai", "codex")),
        ("https://github.com/a/b/blob/main/README.md", ("a", "b")),
        ("https://github.com/a/b/tree/main", ("a", "b")),
        ("https://github.com/a/b.git", ("a", "b")),
    ],
)
def test_reads_owner_and_repo(url, expected):
    assert github_repo_from_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/torvalds",  # a profile, not a repo
        "https://github.com/features/copilot",  # a product page
        "https://gist.github.com/someone/abc123",  # not the repo host
        "https://gitlab.com/a/b",
        "https://example.com/a/b",
        "https://github.com/",
    ],
)
def test_ignores_what_is_not_a_repo(url):
    assert github_repo_from_url(url) is None


# ─── filter_thin_repos ───────────────────────────────────────────────────────


def test_drops_a_repo_nobody_has_starred(monkeypatch):
    """The case this whole gate exists for: a solo repo, posted by its author,
    indistinguishable from a real project by title alone."""
    articles = [_article("https://github.com/someone/llm-thing")]
    kept, _, session = _run(monkeypatch, articles, {("someone", "llm-thing"): 2})
    assert kept == []
    # Recorded, unlike the recency holds in the HN source: a star count does
    # not change inside a 48h window, so re-checking it tomorrow is waste.
    assert session.merged == ["https://github.com/someone/llm-thing"]


def test_keeps_a_repo_that_clears_the_bar(monkeypatch):
    articles = [_article("https://github.com/someone/llm-thing")]
    kept, _, session = _run(monkeypatch, articles, {("someone", "llm-thing"): 4200})
    assert kept == articles
    assert session.merged == []


def test_a_failed_lookup_keeps_the_article(monkeypatch):
    """None is "GitHub did not tell us", not "zero stars". Rate limits and
    timeouts must never delete an article."""
    articles = [_article("https://github.com/someone/llm-thing")]
    kept, _, _ = _run(monkeypatch, articles, {("someone", "llm-thing"): None})
    assert kept == articles


def test_a_known_owner_costs_no_lookup(monkeypatch):
    """A PR against llama.cpp is worth reading on day one, and spending one of
    60 hourly requests to confirm what we already know is waste."""
    articles = [_article("https://github.com/ggml-org/llama.cpp/pull/24219")]
    kept, looked_up, _ = _run(monkeypatch, articles, {})
    assert kept == articles
    assert looked_up == []


def test_non_repo_urls_pass_untouched(monkeypatch):
    articles = [_article("https://openai.com/index/gpt-5-6/")]
    kept, looked_up, _ = _run(monkeypatch, articles, {})
    assert kept == articles
    assert looked_up == []


def test_order_is_preserved_around_a_drop(monkeypatch):
    articles = [
        _article("https://openai.com/index/gpt-5-6/"),
        _article("https://github.com/someone/llm-thing"),
        _article("https://github.com/other/real-tool"),
    ]
    kept, _, _ = _run(
        monkeypatch,
        articles,
        {("someone", "llm-thing"): 2, ("other", "real-tool"): 900},
    )
    assert [a["url"] for a in kept] == [
        "https://openai.com/index/gpt-5-6/",
        "https://github.com/other/real-tool",
    ]


def test_zero_disables_the_gate(monkeypatch):
    articles = [_article("https://github.com/someone/llm-thing")]
    kept, looked_up, _ = _run(
        monkeypatch, articles, {("someone", "llm-thing"): 2}, min_stars=0
    )
    assert kept == articles
    assert looked_up == []
