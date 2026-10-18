"""The nightly collect timer's entrypoint."""

from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from app.features.collect import service as collect

BACKEND = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("code", [0, 1])
def test_the_entrypoint_exits_with_the_runs_code(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    monkeypatch.setattr(collect, "run_nightly", lambda: code)
    with pytest.raises(SystemExit) as exited:
        runpy.run_module("app.entry.cli.collect", run_name="__main__")
    assert exited.value.code == code


def test_the_collect_run_leaves_the_root_logger_alone() -> None:
    # At INFO, httpx logs a line for every request the night makes and buries
    # the run's own progress in the journal.
    probe = (
        "import logging, app.entry.cli.collect; "
        "root = logging.getLogger(); "
        "assert root.level == logging.WARNING and not root.handlers, root"
    )
    subprocess.run([sys.executable, "-c", probe], cwd=BACKEND, check=True)
