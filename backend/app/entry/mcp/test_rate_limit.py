"""The per-user call limit, on a clock the test moves by hand."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from app.entry.mcp.rate_limit import DAY, MINUTE, PER_DAY, PER_MINUTE, UserRateLimit


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


def test_the_minute_limit_refuses_the_call_after_the_last_allowed(
    clock: Clock,
) -> None:
    limit = UserRateLimit(clock)
    for _ in range(PER_MINUTE):
        limit.check("a")
        clock.now += 1

    with pytest.raises(ToolError, match="20 calls a minute. Retry in 40 seconds"):
        limit.check("a")


def test_the_minute_limit_lifts_when_the_oldest_call_ages_out(clock: Clock) -> None:
    limit = UserRateLimit(clock)
    for _ in range(PER_MINUTE):
        limit.check("a")
    clock.now += MINUTE - 1
    with pytest.raises(ToolError, match="Retry in 1 seconds"):
        limit.check("a")

    clock.now += 1
    limit.check("a")


def test_a_refused_call_does_not_push_the_retry_back(clock: Clock) -> None:
    limit = UserRateLimit(clock)
    for _ in range(PER_MINUTE):
        limit.check("a")
    for _ in range(50):
        with pytest.raises(ToolError):
            limit.check("a")

    clock.now += MINUTE
    limit.check("a")


def test_each_user_has_their_own_count(clock: Clock) -> None:
    limit = UserRateLimit(clock)
    for _ in range(PER_MINUTE):
        limit.check("a")

    limit.check("b")


def test_the_day_limit_holds_under_the_minute_limit(clock: Clock) -> None:
    limit = UserRateLimit(clock)
    start = clock.now
    for _ in range(PER_DAY):
        limit.check("a")
        clock.now += MINUTE
    # 500 minutes in, the first call is still inside the day.
    with pytest.raises(ToolError, match="500 calls a day. Retry in 56400 seconds"):
        limit.check("a")

    clock.now = start + DAY
    limit.check("a")
