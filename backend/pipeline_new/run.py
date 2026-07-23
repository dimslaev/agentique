"""CLI entry point: ``python -m pipeline_new.run``.

Opens one session, runs the pipeline, and rolls back on a top-level failure so a
crash mid-run never leaves a half-written transaction behind. Exit code is 1 on
failure so a scheduler can tell a bad run from a good one.
"""

from __future__ import annotations

import sys

from sqlmodel import Session

from pipeline_new.db import get_engine
from pipeline_new.pipeline import run


def main() -> int:
    try:
        with Session(get_engine()) as session:
            try:
                run(session)
            except Exception:
                session.rollback()
                raise
    except Exception as e:
        print(f"Pipeline failed: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
