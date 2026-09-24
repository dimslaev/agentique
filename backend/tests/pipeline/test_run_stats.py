"""What the run records: per-source counts, and the publishers it polled.

On 2026-09-03 the Feeds source died after the fetch and took the per-publisher
record with it, so every feed was invisible on exactly the night something was
wrong. These pin that the publisher bookkeeping survives a failure after the
fetch, that a failed fetch stamps nothing, and that the stored error stays a
readable length.
"""

from __future__ import annotations

from pipeline import run as run_module
from pipeline.runs import RunStats
from pipeline.steps.fetch import Source


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def rollback(self) -> None:
        pass


class _FakeResolver:
    quarantined: list[str] = []

    def __init__(self, **kwargs) -> None:
        pass


def _article(url: str, source: str, publisher_id: int = 1) -> dict:
    return {
        "title": "t",
        "url": url,
        "content": "body",
        "source": source,
        "publisher_id": publisher_id,
    }


def _stub_run(monkeypatch, sources, **overrides):
    """Run the pipeline over ``sources`` with every step a no-op passthrough.
    Returns the stats and what the publisher bookkeeping was handed."""
    seen: dict[str, list] = {"polled": [], "new": []}
    monkeypatch.setattr(run_module, "get_engine", lambda: None)
    monkeypatch.setattr(run_module, "Session", lambda engine: _FakeSession())
    monkeypatch.setattr(run_module, "PublisherResolver", _FakeResolver)
    monkeypatch.setattr(run_module, "build_sources", lambda session: sources)
    monkeypatch.setattr(run_module, "resolve_publishers", lambda a, r: a)
    monkeypatch.setattr(run_module, "filter_known_urls", lambda s, a, label: a)
    monkeypatch.setattr(run_module, "queue_candidates", lambda s, a: a)
    monkeypatch.setattr(
        run_module, "fetch_source", lambda source: (source.fetcher(), {})
    )
    monkeypatch.setattr(
        run_module,
        "record_polled",
        lambda s, names, errors: seen["polled"].append((names, errors)),
    )
    monkeypatch.setattr(
        run_module, "record_new", lambda s, ids: seen["new"].append(sorted(ids))
    )
    for name, value in overrides.items():
        monkeypatch.setattr(run_module, name, value)

    stats = RunStats()
    run_module.run_pipeline(stats)
    return stats, seen


def _feeds_source() -> Source:
    return Source(
        "Feeds",
        lambda: [_article("u1", "Feed A", publisher_id=7)],
        publisher_names=("Feed A", "Feed B"),
    )


def test_a_clean_run_counts_and_stamps(monkeypatch):
    stats, seen = _stub_run(monkeypatch, [_feeds_source()])

    [source] = stats.sources
    assert (source.fetched, source.queued, source.error) == (1, 1, None)
    assert seen["polled"] == [(("Feed A", "Feed B"), {})]
    assert seen["new"] == [[7]]


def test_polled_publishers_are_stamped_after_a_failure_past_the_fetch(monkeypatch):
    def boom(_session, _articles):
        raise RuntimeError("queue down")

    stats, seen = _stub_run(monkeypatch, [_feeds_source()], queue_candidates=boom)

    assert seen["polled"] == [(("Feed A", "Feed B"), {})]
    # Nothing was queued, so nothing is new.
    assert seen["new"] == [[]]
    assert stats.sources[0].error == "RuntimeError: queue down"


def test_a_fetch_that_failed_stamps_no_publisher(monkeypatch):
    """Nothing was polled, so there was no answer to record — stamping every
    publisher as fetched would hide a source that is down."""

    def boom(_source):
        raise RuntimeError("feeds unreachable")

    stats, seen = _stub_run(monkeypatch, [_feeds_source()], fetch_source=boom)

    assert seen["polled"] == []
    assert stats.sources[0].error == "RuntimeError: feeds unreachable"


def test_bookkeeping_that_fails_does_not_fail_the_source(monkeypatch):
    def boom(*_args):
        raise RuntimeError("db gone")

    stats, _ = _stub_run(monkeypatch, [_feeds_source()], record_polled=boom)

    assert (stats.sources[0].queued, stats.sources[0].error) == (1, None)


def test_one_source_failing_does_not_stop_the_next(monkeypatch):
    def boom(_session, articles):
        if articles[0]["source"] == "Feed A":
            raise RuntimeError("queue down")
        return articles

    stats, _ = _stub_run(
        monkeypatch,
        [_feeds_source(), Source("Hacker News", lambda: [_article("u2", "HN")])],
        queue_candidates=boom,
    )

    assert [(s.source, s.queued) for s in stats.sources] == [
        ("Feeds", 0),
        ("Hacker News", 1),
    ]


def test_the_stored_error_is_truncated(monkeypatch):
    def boom(_session, _articles):
        raise RuntimeError("x" * 50_000)

    stats, _ = _stub_run(monkeypatch, [_feeds_source()], queue_candidates=boom)

    error = stats.sources[0].error or ""
    assert len(error) < 1_000
    assert error.endswith("chars]")
