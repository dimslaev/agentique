"""The daily mail: liveness first, then what needs a look, then what landed.

The mail is built from the database alone, so it can say the run never
happened. The shape is the point: problems before articles, every landed
article named, the rejects a count.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.core.db.run import PipelineRun
from app.features.collect.report import (
    STALE_RUN_HOURS,
    Landed,
    Night,
    format_night,
    liveness,
    source_lines,
    subject,
)

NOW = datetime(2026, 9, 23, 6, 0, tzinfo=UTC)


def _run(hours_ago: float, ok: bool = True) -> PipelineRun:
    return PipelineRun(ok=ok, finished_at=NOW - timedelta(hours=hours_ago))


def _night() -> Night:
    return Night(
        liveness=None,
        silent_sources=[],
        source_errors=[],
        failing_publishers=[],
        landed=[
            Landed(
                title="Gemma 4 open model family",
                url="https://deepmind.google/blog/gemma-4",
                score=86,
                publisher="Google DeepMind Blog",
            )
        ],
        rejected=17,
        still_pending=2,
    )


# ─── liveness ────────────────────────────────────────────────────────────────


def test_a_fresh_good_run_is_fine() -> None:
    assert liveness(_run(2), NOW) is None


def test_a_crashed_run_is_said() -> None:
    assert "crashed" in (liveness(_run(2, ok=False), NOW) or "")


def test_a_stale_run_is_said() -> None:
    message = liveness(_run(STALE_RUN_HOURS + 4), NOW) or ""
    assert f"No pipeline run in {STALE_RUN_HOURS + 4}h" in message


def test_no_run_at_all_is_said() -> None:
    assert liveness(None, NOW) == "No pipeline run is recorded."


# ─── sources ─────────────────────────────────────────────────────────────────


def test_silent_sources_and_errors_come_from_the_stored_counts() -> None:
    silent, errors = source_lines(
        [
            {"source": "Feeds", "fetched": 120, "queued": 19, "error": None},
            {"source": "Newsletter", "fetched": 0, "queued": 0, "error": None},
            {"source": "Lab Watch", "fetched": 0, "queued": 0, "error": "boom"},
        ]
    )
    assert silent == ["Newsletter", "Lab Watch"]
    assert errors == ["Lab Watch: boom"]


def test_a_run_recorded_in_the_old_shape_still_reports() -> None:
    """Old rows carry an ``errors`` list and fields that are gone. The mail is
    how a reader finds out the pipeline is unwell, so it cannot be the thing
    that breaks on them."""
    silent, errors = source_lines(
        [{"source": "Feeds", "fetched": 3, "deduped": 1, "errors": ["a", "b"]}]
    )
    assert silent == []
    assert errors == ["Feeds: a", "Feeds: b"]


# ─── the mail ────────────────────────────────────────────────────────────────


def test_what_landed_is_named_one_by_one() -> None:
    body = format_night(_night())
    assert "LANDED (1)" in body
    assert "[86/100] Gemma 4 open model family — Google DeepMind Blog" in body
    assert "https://deepmind.google/blog/gemma-4" in body
    assert "17 turned down." in body
    assert "2 candidate(s) still waiting on a verdict." in body
    assert subject(_night()) == "1 article(s) landed"


def test_a_quiet_night_has_no_problem_section() -> None:
    assert "NEEDS A LOOK" not in format_night(_night())
    assert "PIPELINE" not in format_night(_night())


def test_problems_come_before_the_articles() -> None:
    body = format_night(
        replace(
            _night(),
            liveness="The last run crashed (2026-09-23 04:10 UTC).",
            silent_sources=["Newsletter"],
            source_errors=["Lab Watch: boom"],
            failing_publishers=[("Cloudflare", "RuntimeError: Status code 403")],
        )
    )
    assert body.index("PIPELINE") < body.index("NEEDS A LOOK") < body.index("LANDED")
    assert "Newsletter fetched nothing." in body
    assert "Lab Watch: boom" in body
    assert "Cloudflare: RuntimeError: Status code 403" in body
    assert subject(replace(_night(), liveness="x")) == "Pipeline needs a look"


def test_an_empty_night_says_where_to_look() -> None:
    body = format_night(replace(_night(), landed=[], rejected=0, still_pending=40))
    assert "LANDED (0)" in body
    assert "curation session" in body
    assert "40 candidate(s) still waiting" in body
    assert subject(replace(_night(), landed=[])) == "Nothing landed"


def test_an_empty_queue_is_said_plainly() -> None:
    assert "Queue empty" in format_night(replace(_night(), still_pending=0))
