"""Nightly report entry point. Run with: python -m pipeline.report

Sent after the curation agent, not after the fetch: the 04:00 run queues
candidates and lands nothing, so a report at that hour would be a page of
counts an hour before the articles exist. This reads the night out of the
database — what the agent published, how much it turned down, what is still
waiting — and emails it.

Runs on its own timer rather than after the agent's session, so a night the
agent never ran still produces a report, and that report says nothing landed.
"""

from __future__ import annotations

import sys

from sqlmodel import Session

from pipeline.db import get_engine
from pipeline.health import report_curation

if __name__ == "__main__":
    try:
        with Session(get_engine()) as session:
            report_curation(session)
    except Exception as e:
        print(f"Curation report failed: {e}", file=sys.stderr)
        sys.exit(1)
