"""Capping the error string that lands in a run row and the alert email."""

from __future__ import annotations

from app.platform.logging import short_error


def test_short_error_names_the_type_and_the_message():
    assert short_error(ValueError("bad input")) == "ValueError: bad input"


def test_short_error_collapses_a_multi_line_message():
    """A provider error arrives as a wall of prompt and HTML — one line of it
    is what lands in the run row and the alert email."""
    assert short_error(RuntimeError("failed\n  attempt 0\n  attempt 1")) == (
        "RuntimeError: failed attempt 0 attempt 1"
    )


def test_short_error_truncates_past_the_limit_and_says_so():
    out = short_error(RuntimeError("x" * 5000), limit=100)
    assert out.startswith("RuntimeError: " + "x" * 80)
    assert out.endswith("[truncated, 5014 chars]")
    assert len(out) < 200


def test_short_error_leaves_a_message_at_the_limit_alone():
    message = "y" * (100 - len("ValueError: "))
    assert short_error(ValueError(message), limit=100) == f"ValueError: {message}"
