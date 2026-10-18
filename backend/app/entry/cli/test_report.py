"""The daily report timer's entrypoint."""

from __future__ import annotations

import runpy

import pytest

from app.features.collect import service as collect


@pytest.mark.parametrize("code", [0, 1])
def test_the_entrypoint_exits_with_the_reports_code(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    monkeypatch.setattr(collect, "send_report", lambda: code)
    with pytest.raises(SystemExit) as exited:
        runpy.run_module("app.entry.cli.report", run_name="__main__")
    assert exited.value.code == code
