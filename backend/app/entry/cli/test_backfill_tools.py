"""The verdict reader of the tools backfill."""

from __future__ import annotations

from pathlib import Path

from app.entry.cli.backfill_tools import _verdicts


def test_verdicts_keeps_the_json_lines_and_drops_the_rest(tmp_path: Path) -> None:
    path = tmp_path / "verdicts.jsonl"
    path.write_text('Here you go:\n{"repo": "a/b", "keep": true}\n{"repo": \n```\n')

    assert _verdicts(path) == [{"repo": "a/b", "keep": True}]
