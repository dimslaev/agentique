"""What the run records: what it queued, and what survives a source that fails
partway through.

On 2026-09-03 the Feeds source died at the scoring step and took the
record_publishers call with it: the run stored 19 publishers instead of 118,
so every feed was invisible to the verifier on exactly the night something was
wrong. These pin that the per-publisher counts survive a failure after the
fetch, and that the stored error stays a readable length.
"""

from __future__ import annotations

from pipeline import run as run_module
from pipeline.health import RunStats, _format_report
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


def _article(url: str, source: str, title: str = "t") -> dict:
    return {"title": title, "url": url, "content": "body", "source": source}


def _stub_run(monkeypatch, sources, **overrides):
    """Run the pipeline over ``sources`` with every step a no-op passthrough."""
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
    for name, value in overrides.items():
        monkeypatch.setattr(run_module, name, value)

    stats = RunStats()
    run_module.run_pipeline(stats)
    return stats


def _feeds_source() -> Source:
    return Source(
        "Feeds",
        lambda: [_article("u1", "Feed A")],
        publisher_names=("Feed A", "Feed B"),
    )


def test_publisher_counts_survive_a_failure_after_the_fetch(monkeypatch):
    def boom(_session, _articles):
        raise RuntimeError("queue down")

    stats = _stub_run(monkeypatch, [_feeds_source()], queue_candidates=boom)

    assert [p.name for p in stats.publishers] == ["Feed A", "Feed B"]
    assert [p.fetched for p in stats.publishers] == [1, 0]
    assert len(stats.sources[0].errors) == 1


def test_a_fetch_that_failed_records_no_publisher_counts(monkeypatch):
    """Nothing was polled, so there are no counts — reporting 0 fetched for
    every publisher would alert on each one for a single source-level error."""

    def boom(_source):
        raise RuntimeError("feeds unreachable")

    stats = _stub_run(monkeypatch, [_feeds_source()], fetch_source=boom)

    assert stats.publishers == []
    assert len(stats.sources[0].errors) == 1


def test_a_clean_run_still_records_its_publishers(monkeypatch):
    stats = _stub_run(monkeypatch, [_feeds_source()])

    assert [(p.name, p.fetched) for p in stats.publishers] == [
        ("Feed A", 1),
        ("Feed B", 0),
    ]
    assert stats.sources[0].errors == []


def test_one_source_failing_does_not_stop_the_next(monkeypatch):
    def boom(_session, articles):
        if articles[0]["source"] == "Feed A":
            raise RuntimeError("queue down")
        return articles

    stats = _stub_run(
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

    stats = _stub_run(monkeypatch, [_feeds_source()], queue_candidates=boom)

    error = stats.sources[0].errors[0]
    assert len(error) < 1_000
    assert error.endswith("chars]")


def test_the_report_lists_errors(monkeypatch):
    def boom(_session, _articles):
        raise RuntimeError("queue down")

    stats = _stub_run(monkeypatch, [_feeds_source()], queue_candidates=boom)
    stats.finish(ok=True)

    report = _format_report(stats)

    assert "ERRORS" in report
    assert "Feeds: RuntimeError: queue down" in report


def test_the_run_queues_its_survivors(monkeypatch):
    """The agent is the judge, so the night's run ends at a pending row."""
    stats = _stub_run(monkeypatch, [_feeds_source()])

    [source] = stats.sources
    assert source.queued == 1


def test_the_report_says_what_is_waiting(monkeypatch):
    stats = _stub_run(monkeypatch, [_feeds_source()])

    report = _format_report(stats)
    assert "1 candidate(s) queued for review" in report
    assert "→ queued 1" in report
