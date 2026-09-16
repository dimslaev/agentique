"""The night's one email: what landed, and a short account of what did not.

The shape is the point. Every article that landed is named, because that is the
part a reader reads. The ones that did not are a count and the loudest few
publishers — twenty rejects listed one per line was the part of the old report
nobody read, and the verdicts are in the ledger for anyone who wants them.
"""

from __future__ import annotations

from pipeline.health import (
    CurationDay,
    InsertedArticle,
    SourceStats,
    _format_curation,
    _source_stats,
)
from pipeline.models import PipelineRun


def _day(**overrides) -> CurationDay:
    day = CurationDay(
        approved=[
            InsertedArticle(
                id=1,
                title="Gemma 4 open model family",
                url="https://deepmind.google/blog/gemma-4",
                score=86,
                publisher="Google DeepMind Blog",
            )
        ],
        rejected=17,
        loudest=[("MarkTechPost", 4), ("AWS Machine Learning", 3)],
        still_pending=2,
        sources=[SourceStats(source="Feeds", fetched=120, queued=19)],
        errors=[],
    )
    return CurationDay(**{**day.__dict__, **overrides})


def test_what_landed_is_named_one_by_one():
    report = _format_curation(_day())
    assert "LANDED (1)" in report
    assert "[86/100] Gemma 4 open model family — Google DeepMind Blog" in report
    assert "https://deepmind.google/blog/gemma-4" in report


def test_what_did_not_land_is_counted_not_listed():
    report = _format_curation(_day())
    assert "17 turned down. Loudest: MarkTechPost 4, AWS Machine Learning 3." in report
    assert "2 candidate(s) still waiting on a verdict." in report
    # No URLs but the ones that landed: a reject never gets a line of its own.
    assert report.count("https://") == 1


def test_an_empty_night_says_where_to_look():
    """Nothing published is either a quiet night or a curation session that did
    not run, and the report should not leave a reader guessing which."""
    report = _format_curation(_day(approved=[], rejected=0, still_pending=40))
    assert "LANDED (0)" in report
    assert "curation session" in report
    assert "40 candidate(s) still waiting" in report


def test_an_empty_queue_is_said_plainly():
    report = _format_curation(_day(still_pending=0))
    assert "Queue empty" in report


def test_the_funnel_and_the_errors_come_from_the_recorded_run():
    report = _format_curation(_day(errors=["Feeds: RuntimeError: boom"]))
    assert "Feeds: fetched 120" in report
    assert "→ queued 19" in report
    assert "- Feeds: RuntimeError: boom" in report


def test_a_run_recorded_before_a_counter_existed_still_reports():
    """`pipeline_run.sources` is stored JSON, and old rows predate `queued`.
    Rebuilding must not fail on them — the report is how a reader finds out the
    pipeline is unwell, so it cannot be the thing that breaks."""
    run = PipelineRun(
        sources=[{"source": "Feeds", "fetched": 3, "gone_field": 1}], publishers=[]
    )
    [rebuilt] = _source_stats(run)
    assert (rebuilt.source, rebuilt.fetched, rebuilt.queued) == ("Feeds", 3, 0)


def test_no_recorded_run_is_no_funnel_rather_than_a_crash():
    assert _source_stats(None) == []
