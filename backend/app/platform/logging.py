"""Stdout progress logging, pacing, and error-string capping for long jobs.

The pipeline runs under systemd and is read through journald, so progress goes
to stdout rather than through the ``logging`` module's handlers.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

# Cap on a stored/emailed error string - see ``short_error``.
ERROR_CHARS = 500


def log(message: str) -> None:
    ts = datetime.now(UTC).isoformat()
    print(f"[{ts}] {message}")  # noqa: T201


def wait_ms(ms: int) -> None:
    time.sleep(ms / 1000)


def short_error(e: BaseException, limit: int = ERROR_CHARS) -> str:
    """``Type: message`` for an exception, capped at ``limit`` characters.

    A provider error is not always one line: a BAML failure carries every
    attempt's rendered prompt and whatever HTML the upstream served, which is
    tens of KB. That text is stored in ``pipeline_run.sources`` and emailed by
    the verifier, so it gets cut here rather than at each call site.
    """
    message = f"{type(e).__name__}: {e}"
    collapsed = " ".join(message.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit]}... [truncated, {len(collapsed)} chars]"
