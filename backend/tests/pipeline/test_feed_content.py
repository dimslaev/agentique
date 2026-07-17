"""Feed content extraction + the re-fetch gate.

Both bugs these cover failed silently in prod: bare Substack links parsed to
zero entries (35 of 65 feeds produced nothing), and full text sitting unused in
content:encoded while the pipeline re-fetched the URL and summarized a teaser.
"""

from __future__ import annotations

import pytest

from pipeline.heuristics import MIN_CONTENT_CHARS
from pipeline.sources.substack import _entry_content
from pipeline.utils import feed_url

# Varied prose on purpose: trafilatura deduplicates repeated segments, so a
# fixture built from one repeated sentence extracts to nothing.
_ARTICLE_HTML = """
<div>
  <p>Anthropic shipped a new model today with a longer context window and
  noticeably faster tool use. The release lands three months after the previous
  flagship and targets developers building agents.</p>
  <p>Pricing drops to five dollars per million input tokens, roughly a third of
  what the earlier generation cost. Cache reads are discounted further, which
  matters for long-running agent loops that replay the same prefix.</p>
  <p>Benchmarks put it ahead on agentic coding tasks, though the gap narrows on
  pure reasoning evaluations. Independent numbers are not yet available, and the
  company has not published the evaluation harness.</p>
  <p>Availability starts today through the API and the desktop apps. Enterprise
  customers get access next week, with fine-tuning promised before the end of
  the quarter.</p>
</div>
"""


@pytest.mark.parametrize(
    "given, expected",
    [
        ("https://linas.substack.com", "https://linas.substack.com/feed"),
        ("https://linas.substack.com/", "https://linas.substack.com/feed"),
        # already a feed URL — leave it alone
        ("https://importai.substack.com/feed", "https://importai.substack.com/feed"),
        # non-Substack hosts keep whatever the publisher configured
        (
            "https://huggingface.co/blog/feed.xml",
            "https://huggingface.co/blog/feed.xml",
        ),
        ("https://console.dev/rss.xml", "https://console.dev/rss.xml"),
    ],
)
def test_feed_url_normalises_bare_substack_links(given, expected):
    assert feed_url(given) == expected


@pytest.mark.parametrize(
    "given, expected",
    [
        # a substack-platform link on a custom domain: the host gives nothing
        # away, so only the platform flag says it needs /feed
        ("https://www.latent.space", "https://www.latent.space/feed"),
        ("https://www.latent.space/", "https://www.latent.space/feed"),
        ("https://www.latent.space/feed", "https://www.latent.space/feed"),
    ],
)
def test_feed_url_appends_feed_for_substack_platform_links(given, expected):
    assert feed_url(given, is_substack=True) == expected


def test_feed_url_is_idempotent():
    """Applied by publisher config and again by the fetcher — must not double up."""
    once = feed_url("https://linas.substack.com")
    assert feed_url(once) == once


def test_content_encoded_preferred_over_summary_teaser():
    entry = {
        "summary": "<p>A short teaser.</p>",
        "content": [{"value": _ARTICLE_HTML}],
    }
    text = _entry_content(entry)
    assert len(text) >= MIN_CONTENT_CHARS
    assert "longer context window" in text
    assert "A short teaser" not in text


def test_falls_back_to_summary_when_no_content_encoded():
    entry = {"summary": _ARTICLE_HTML, "content": []}
    text = _entry_content(entry)
    assert len(text) >= MIN_CONTENT_CHARS


def test_html_is_stripped_not_stored_raw():
    entry = {"summary": "", "content": [{"value": _ARTICLE_HTML}]}
    text = _entry_content(entry)
    assert "<p>" not in text and "<div>" not in text


def test_short_teaser_yields_empty_rather_than_pretending_to_be_content():
    """A teaser must not masquerade as an article — the gate reads its length."""
    entry = {"summary": "<p>Read more at the link.</p>", "content": []}
    assert _entry_content(entry) == ""


def test_missing_fields_do_not_raise():
    assert _entry_content({}) == ""
