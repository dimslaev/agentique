"""What the run records: per-source counts, and the publishers it polled.

On 2026-09-03 the Feeds source died after the fetch and took the per-publisher
record with it, so every feed was invisible on exactly the night something was
wrong. These pin that the publisher bookkeeping survives a failure after the
fetch, that a failed fetch stamps nothing, that one source failing leaves the
others running, and that the stored error stays a readable length.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import pytest

from app.features.collect import service as run_module
from app.features.collect.fetch import Source
from app.features.collect.model import Candidate, RawItem, RunStats


class _FakeSession:
    def __init__(self) -> None:
        self.rollbacks = 0

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def rollback(self) -> None:
        self.rollbacks += 1


class _FakeResolver:
    quarantined: list[str] = []
    created: list[str] = []

    def __init__(self, **kwargs: object) -> None:
        pass


def _article(url: str, source: str, publisher_id: int = 1) -> Candidate:
    return {
        "title": "t",
        "url": url,
        "content": "body",
        "published_date": None,
        "source": source,
        "publisher_id": publisher_id,
    }


def _source(
    label: str, *articles: Candidate, publisher_names: tuple[str, ...] = ()
) -> Source:
    return Source(label, lambda: (list(articles), {}), publisher_names)


@dataclass
class _Seen:
    """What the publisher bookkeeping was handed, and the session the run used."""

    polled: list[tuple[Iterable[str], dict[str, str]]] = field(default_factory=list)
    new: list[list[int]] = field(default_factory=list)
    session: _FakeSession = field(default_factory=_FakeSession)


def _stub_run(
    monkeypatch: pytest.MonkeyPatch,
    sources: list[Source],
    **overrides: object,
) -> tuple[RunStats, _Seen]:
    """Run collect over ``sources`` with every step a no-op passthrough."""
    seen = _Seen()

    def record_polled(
        _session: object, names: Iterable[str], errors: dict[str, str]
    ) -> None:
        seen.polled.append((names, errors))

    def record_new(_session: object, ids: Iterable[int]) -> None:
        seen.new.append(sorted(ids))

    def resolve(articles: list[RawItem], _resolver: object) -> list[RawItem]:
        return articles

    def passthrough(_session: object, articles: list[Candidate]) -> list[Candidate]:
        return articles

    def keep(_session: object, articles: list[RawItem], _label: str) -> list[RawItem]:
        return articles

    monkeypatch.setattr(run_module, "engine", None)
    monkeypatch.setattr(run_module, "Session", lambda engine: seen.session)
    monkeypatch.setattr(run_module, "PublisherResolver", _FakeResolver)
    monkeypatch.setattr(run_module, "build_sources", lambda session: sources)
    monkeypatch.setattr(run_module, "resolve_publishers", resolve)
    monkeypatch.setattr(run_module, "filter_known_urls", keep)
    monkeypatch.setattr(run_module, "queue_candidates", passthrough)
    monkeypatch.setattr(run_module, "fetch_source", lambda source: source.fetcher())
    monkeypatch.setattr(run_module, "record_polled", record_polled)
    monkeypatch.setattr(run_module, "record_new", record_new)
    for name, value in overrides.items():
        monkeypatch.setattr(run_module, name, value)

    stats = RunStats()
    run_module.run(stats)
    return stats, seen


def _feeds_source() -> Source:
    return _source(
        "Feeds",
        _article("u1", "Feed A", publisher_id=7),
        publisher_names=("Feed A", "Feed B"),
    )


def test_a_clean_run_counts_and_stamps(monkeypatch: pytest.MonkeyPatch) -> None:
    stats, seen = _stub_run(monkeypatch, [_feeds_source()])

    [source] = stats.sources
    assert (source.fetched, source.queued, source.error) == (1, 1, None)
    assert seen.polled == [(("Feed A", "Feed B"), {})]
    assert seen.new == [[7]]


def test_polled_publishers_are_stamped_after_a_failure_past_the_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_session: object, _articles: object) -> list[Candidate]:
        raise RuntimeError("queue down")

    stats, seen = _stub_run(monkeypatch, [_feeds_source()], queue_candidates=boom)

    assert seen.polled == [(("Feed A", "Feed B"), {})]
    # Nothing was queued, so nothing is new.
    assert seen.new == [[]]
    assert stats.sources[0].error == "RuntimeError: queue down"


def test_a_fetch_that_failed_stamps_no_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing was polled, so there was no answer to record — stamping every
    publisher as fetched would hide a source that is down."""

    def boom(_source: object) -> tuple[list[RawItem], dict[str, str]]:
        raise RuntimeError("feeds unreachable")

    stats, seen = _stub_run(monkeypatch, [_feeds_source()], fetch_source=boom)

    assert seen.polled == []
    assert stats.sources[0].error == "RuntimeError: feeds unreachable"


def test_a_failed_source_rolls_its_session_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The next source shares the session; a failed flush left in it would
    fail every source after it."""

    def boom(_session: object, _articles: object) -> list[Candidate]:
        raise RuntimeError("queue down")

    _, seen = _stub_run(monkeypatch, [_feeds_source()], queue_candidates=boom)

    assert seen.session.rollbacks == 1


def test_the_errors_a_fetch_reports_reach_the_bookkeeping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fetch(_source: object) -> tuple[list[RawItem], dict[str, str]]:
        return [], {"Feed B": "RuntimeError: Status code 403"}

    _, seen = _stub_run(monkeypatch, [_feeds_source()], fetch_source=fetch)

    assert seen.polled == [
        (("Feed A", "Feed B"), {"Feed B": "RuntimeError: Status code 403"})
    ]


def test_bookkeeping_that_fails_does_not_fail_the_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: object) -> None:
        raise RuntimeError("db gone")

    stats, _ = _stub_run(monkeypatch, [_feeds_source()], record_polled=boom)

    assert (stats.sources[0].queued, stats.sources[0].error) == (1, None)


def test_one_source_failing_does_not_stop_the_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(_session: object, articles: list[Candidate]) -> list[Candidate]:
        if articles[0]["source"] == "Feed A":
            raise RuntimeError("queue down")
        return articles

    stats, seen = _stub_run(
        monkeypatch,
        [_feeds_source(), _source("Hacker News", _article("u2", "HN"))],
        queue_candidates=boom,
    )

    assert [(s.source, s.queued, s.error) for s in stats.sources] == [
        ("Feeds", 0, "RuntimeError: queue down"),
        ("Hacker News", 1, None),
    ]
    assert seen.new == [[], [1]]


def test_the_stored_error_is_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_session: object, _articles: object) -> list[Candidate]:
        raise RuntimeError("x" * 50_000)

    stats, _ = _stub_run(monkeypatch, [_feeds_source()], queue_candidates=boom)

    error = stats.sources[0].error or ""
    assert len(error) < 1_000
    assert error.endswith("chars]")


# ─── run_nightly ─────────────────────────────────────────────────────────────


def _stub_nightly(
    monkeypatch: pytest.MonkeyPatch,
    run: Callable[[RunStats], None],
    record: Callable[[object, RunStats], object] | None = None,
) -> list[RunStats]:
    recorded: list[RunStats] = []

    def record_run(_session: object, stats: RunStats) -> None:
        recorded.append(stats)

    monkeypatch.setattr(run_module, "engine", None)
    monkeypatch.setattr(run_module, "Session", lambda engine: _FakeSession())
    monkeypatch.setattr(run_module, "run", run)
    monkeypatch.setattr(run_module, "record_run", record or record_run)
    return recorded


def test_a_clean_night_exits_zero_and_records_an_ok_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded = _stub_nightly(monkeypatch, lambda stats: None)

    assert run_module.run_nightly() == 0
    [stats] = recorded
    assert stats.ok and stats.finished_at is not None


def test_a_crash_exits_one_and_is_still_recorded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The daily mail reads the recorded row: a crash that recorded nothing
    would read as a run that never happened."""

    def crash(_stats: RunStats) -> None:
        raise RuntimeError("db unreachable")

    recorded = _stub_nightly(monkeypatch, crash)

    assert run_module.run_nightly() == 1
    [stats] = recorded
    assert not stats.ok


def test_recording_that_fails_does_not_flip_the_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_session: object, _stats: RunStats) -> None:
        raise RuntimeError("db gone")

    _stub_nightly(monkeypatch, lambda stats: None, record=broken)

    assert run_module.run_nightly() == 0


# ─── send_report ─────────────────────────────────────────────────────────────


def test_a_report_that_cannot_be_read_exits_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_session: object) -> None:
        raise RuntimeError("db gone")

    monkeypatch.setattr(run_module, "engine", None)
    monkeypatch.setattr(run_module, "Session", lambda engine: _FakeSession())
    monkeypatch.setattr(run_module, "read_night", broken)

    assert run_module.send_report() == 1


def test_a_report_is_read_from_the_db_and_mailed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        run_module, "send_mail", lambda subject, body: sent.append((subject, body))
    )

    assert run_module.send_report() == 0
    [(subject, body)] = sent
    assert subject and body


def test_a_report_that_cannot_be_sent_exits_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tried: list[str] = []

    def broken(subject: str, _body: str) -> None:
        tried.append(subject)
        raise RuntimeError("resend down")

    monkeypatch.setattr(run_module, "send_mail", broken)

    assert run_module.send_report() == 1
    assert len(tried) == 1
