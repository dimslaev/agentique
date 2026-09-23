"""The pure cores of the fetch and persist steps.

These carry the decisions that silently change what gets published — which
article wins a duplicate URL, whose article it is — so they are pulled out of
the I/O steps and pinned here.
"""

from __future__ import annotations

from pipeline.steps import fetch as fetch_step
from pipeline.steps.persist import best_per_url


def _article(url: str, source: str = "Hacker News", **extra) -> dict:
    return {"title": "A title", "url": url, "source": source, **extra}


# ─── best_per_url ────────────────────────────────────────────────────────────


def test_same_url_from_two_sources_keeps_the_higher_score():
    """Two sources can surface one URL in a run (an HN post and a feed item for
    the same post); the URL is the identity, so the better score wins."""
    items = [
        _article("dupe", source="Hacker News", score=40),
        _article("dupe", source="Feeds", score=90),
    ]
    best = best_per_url(items)
    assert len(best) == 1
    assert best[0]["score"] == 90
    assert best[0]["source"] == "Feeds"


def test_higher_score_wins_regardless_of_order():
    items = [_article("dupe", score=90), _article("dupe", score=40)]
    assert best_per_url(items)[0]["score"] == 90


def test_distinct_urls_all_survive():
    items = [_article("u1", score=80), _article("u2", score=70)]
    assert len(best_per_url(items)) == 2


def test_empty_input():
    assert best_per_url([]) == []


# ─── resolve_publishers ──────────────────────────────────────────────────────


def _raw(url: str, source: str) -> dict:
    return {
        "title": "A title",
        "url": url,
        "content": "body",
        "published_date": None,
        "source": source,
    }


class _FakePublisher:
    def __init__(self, id_: int = 1) -> None:
        self.id = id_


class _FakeResolver:
    def __init__(self, credited: dict | None = None) -> None:
        self._publisher = _FakePublisher()
        self._credited = credited or {}

    def credit(self, url: str) -> _FakePublisher | None:
        return self._credited.get(url)

    def resolve(self, source: str) -> _FakePublisher:
        return self._publisher


def test_every_item_is_stamped_with_its_publisher():
    """resolve_publishers is the only producer of a Candidate, so pin that it
    stamps every item it returns."""
    resolver = _FakeResolver()
    candidates = fetch_step.resolve_publishers(
        [_raw("u1", "Feed A"), _raw("u2", "Feed B")], resolver
    )
    assert [c["publisher_id"] for c in candidates] == [1, 1]


def test_credits_the_author_over_the_aggregator_that_found_it():
    """A post found through Hacker News is the author's when we know their
    site; the source stays Hacker News, which is where we found it."""
    author = _FakePublisher(id_=7)
    url = "https://simonwillison.net/2026/Aug/8/auto-mode/"
    resolver = _FakeResolver(credited={url: author})

    [c] = fetch_step.resolve_publishers([_raw(url, "Hacker News")], resolver)

    assert c["publisher_id"] == 7
    assert c["source"] == "Hacker News"


# ─── build_sources ───────────────────────────────────────────────────────────
# Which channels are live is a one-line edit that silently changes the whole
# funnel's reach, so it is pinned rather than left to review.


def _stub_db_sources(
    monkeypatch,
    feeds: list[dict],
    lab_watch: list[tuple[str, str]],
    newsletter: list[tuple[str, str]] | None = None,
):
    monkeypatch.setattr(fetch_step, "feed_sources_from_db", lambda session: feeds)
    monkeypatch.setattr(
        fetch_step, "lab_watch_targets_from_db", lambda session: lab_watch
    )
    monkeypatch.setattr(
        fetch_step, "newsletter_senders_from_db", lambda session: newsletter or []
    )


def test_every_channel_is_polled(monkeypatch):
    _stub_db_sources(monkeypatch, [], [])
    labels = [s.label for s in fetch_step.build_sources(session=None)]
    assert labels == [
        "Feeds",
        "Hacker News",
        "Newsletter",
        "Lab Watch",
    ]


def test_lab_watch_reports_its_targets_as_publishers(monkeypatch):
    """Per-publisher health needs the full expected set, so a lab that returned
    nothing still gets a row instead of vanishing from the stats."""
    _stub_db_sources(monkeypatch, [], [("Anthropic", "anthropic.com")])
    lab_watch = next(
        s for s in fetch_step.build_sources(session=None) if s.label == "Lab Watch"
    )
    assert lab_watch.publisher_names == ("Anthropic",)


def test_feeds_reports_its_publishers(monkeypatch):
    _stub_db_sources(monkeypatch, [{"name": "Cloudflare", "rssUrl": "x"}], [])
    feeds = next(
        s for s in fetch_step.build_sources(session=None) if s.label == "Feeds"
    )
    assert feeds.publisher_names == ("Cloudflare",)


def test_each_source_binds_its_own_db_config(monkeypatch):
    """The fetchers are lambdas closing over lists read once per run — a shared
    or late-bound one would poll the wrong set."""
    _stub_db_sources(
        monkeypatch,
        [],
        [("Anthropic", "anthropic.com")],
        newsletter=[("@tldr.tech", "TLDR")],
    )
    monkeypatch.setattr(fetch_step, "fetch_lab_watch", lambda targets: targets)
    monkeypatch.setattr(fetch_step, "fetch_newsletter", lambda senders: senders)
    sources = {s.label: s for s in fetch_step.build_sources(session=None)}
    assert sources["Lab Watch"].fetcher() == ([("Anthropic", "anthropic.com")], {})
    assert sources["Newsletter"].fetcher() == ([("@tldr.tech", "TLDR")], {})
