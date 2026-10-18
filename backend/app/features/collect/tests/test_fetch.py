"""The pure cores of the fetch step.

These carry the decisions that silently change what gets queued — whose
article it is, which URLs are never fetched, which channels are polled — so
they are pulled out of the I/O and pinned here.
"""

from __future__ import annotations

from typing import cast

import pytest
from sqlmodel import Session

from app.core.db.publisher import Publisher, PublisherKind
from app.features.collect import fetch as fetch_step
from app.features.collect.model import FeedSource, RawItem
from app.features.collect.publishers import PublisherResolver

# `build_sources` hands the session to the db reads, which these tests stub.
NO_SESSION = cast(Session, None)


# ─── resolve_publishers ──────────────────────────────────────────────────────


def _raw(url: str, source: str) -> RawItem:
    return {
        "title": "A title",
        "url": url,
        "content": "body",
        "published_date": None,
        "source": source,
    }


class _FakeResolver:
    def __init__(self, credited: dict[str, Publisher] | None = None) -> None:
        self._publisher = Publisher(
            id=1, slug="feed", name="Feed", kind=PublisherKind.media
        )
        self._credited = credited or {}

    def publisher_for(self, url: str, source: str) -> Publisher:
        return self._credited.get(url) or self._publisher

    @property
    def resolver(self) -> PublisherResolver:
        return cast(PublisherResolver, self)


def test_every_item_is_stamped_with_its_publisher() -> None:
    """resolve_publishers is the only producer of a Candidate, so pin that it
    stamps every item it returns."""
    resolver = _FakeResolver()
    candidates = fetch_step.resolve_publishers(
        [_raw("u1", "Feed A"), _raw("u2", "Feed B")], resolver.resolver
    )
    assert [c["publisher_id"] for c in candidates] == [1, 1]


def test_credits_the_author_over_the_aggregator_that_found_it() -> None:
    """A post found through Hacker News is the author's when we know their
    site; the source stays Hacker News, which is where we found it."""
    author = Publisher(id=7, slug="simon", name="Simon", kind=PublisherKind.individual)
    url = "https://simonwillison.net/2026/Aug/8/auto-mode/"
    resolver = _FakeResolver(credited={url: author})

    [c] = fetch_step.resolve_publishers([_raw(url, "Hacker News")], resolver.resolver)

    assert c["publisher_id"] == 7
    assert c["source"] == "Hacker News"


# ─── _without_noise ──────────────────────────────────────────────────────────
# A URL-only gate: what it drops is never fetched, so a wrong pattern silently
# costs the feed articles nobody ever sees queued.


def _urls(urls: list[str]) -> list[str]:
    kept = fetch_step._without_noise([_raw(u, "Feeds") for u in urls], "Feeds")
    return [a["url"] for a in kept]


def test_a_glossary_entry_is_dropped_before_it_is_fetched() -> None:
    """AI Hero's dictionary emits one entry per term; the agent rejected 71 of
    them with the same sentence before this gate existed."""
    assert _urls(["https://www.aihero.dev/ai-coding-dictionary/sycophancy"]) == []
    assert _urls(["https://www.aihero.dev/ai-coding-dictionary"]) == []


@pytest.mark.parametrize(
    "url",
    [
        "https://luma.com/horizonagentshack",
        "https://lu.ma/abc",
        "https://partiful.com/e/xyz",
        "https://www.eventbrite.com/e/123",
    ],
)
def test_an_event_page_is_dropped(url: str) -> None:
    assert _urls([url]) == []


def test_an_article_that_only_mentions_a_glossary_survives() -> None:
    kept = "https://example.com/blog/a-glossary-of-agent-terms-explained"
    assert _urls([kept]) == [kept]


def test_ordinary_articles_are_untouched() -> None:
    urls = ["https://example.com/a", "https://example.com/b"]
    assert _urls(urls) == urls


# ─── build_sources ───────────────────────────────────────────────────────────
# Which channels are live is a one-line edit that silently changes the whole
# funnel's reach, so it is pinned rather than left to review.


def _stub_db_sources(
    monkeypatch: pytest.MonkeyPatch,
    feeds: list[FeedSource],
    lab_watch: list[tuple[str, str]],
    newsletter: list[tuple[str, str]] | None = None,
) -> None:
    monkeypatch.setattr(fetch_step, "feed_sources_from_db", lambda session: feeds)
    monkeypatch.setattr(
        fetch_step, "lab_watch_targets_from_db", lambda session: lab_watch
    )
    monkeypatch.setattr(
        fetch_step, "newsletter_senders_from_db", lambda session: newsletter or []
    )


def test_every_channel_is_polled(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_db_sources(monkeypatch, [], [])
    labels = [s.label for s in fetch_step.build_sources(NO_SESSION)]
    assert labels == [
        "Feeds",
        "Hacker News",
        "Newsletter",
        "Lab Watch",
    ]


def test_lab_watch_reports_its_targets_as_publishers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-publisher health needs the full expected set, so a lab that returned
    nothing still gets a row instead of vanishing from the stats."""
    _stub_db_sources(monkeypatch, [], [("Anthropic", "anthropic.com")])
    lab_watch = next(
        s for s in fetch_step.build_sources(NO_SESSION) if s.label == "Lab Watch"
    )
    assert lab_watch.publisher_names == ("Anthropic",)


def test_feeds_reports_its_publishers(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_db_sources(monkeypatch, [{"name": "Cloudflare", "rssUrl": "x"}], [])
    feeds = next(s for s in fetch_step.build_sources(NO_SESSION) if s.label == "Feeds")
    assert feeds.publisher_names == ("Cloudflare",)


def test_each_source_binds_its_own_db_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fetchers are lambdas closing over lists read once per run — a shared
    or late-bound one would poll the wrong set."""
    _stub_db_sources(
        monkeypatch,
        [],
        [("Anthropic", "anthropic.com")],
        newsletter=[("@tldr.tech", "TLDR")],
    )
    monkeypatch.setattr(
        fetch_step, "fetch_lab_watch", lambda targets: [_raw(d, n) for n, d in targets]
    )
    monkeypatch.setattr(
        fetch_step, "fetch_newsletter", lambda senders: [_raw(p, n) for p, n in senders]
    )
    sources = {s.label: s for s in fetch_step.build_sources(NO_SESSION)}
    assert sources["Lab Watch"].fetcher() == ([_raw("anthropic.com", "Anthropic")], {})
    assert sources["Newsletter"].fetcher() == ([_raw("@tldr.tech", "TLDR")], {})
