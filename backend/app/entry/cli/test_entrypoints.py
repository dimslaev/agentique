"""What systemd, the deploy and prestart.sh run: that each target exists."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]
REPO = BACKEND.parent
SHELL_SCRIPTS = (
    BACKEND / "app/entry/cli/prestart.sh",
    REPO / "scripts/tests-start.sh",
)


@pytest.mark.parametrize(
    "unit", sorted((REPO / "deploy").glob("*.service")), ids=lambda p: p.name
)
def test_every_python_unit_starts_something_that_exists(unit: Path) -> None:
    # The units run from /opt/agentique/backend. A renamed module fails there
    # only when the timer fires, at night.
    for line in unit.read_text().splitlines():
        if not line.startswith("ExecStart=") or "/python " not in line:
            continue
        args = line.split()[1:]
        if args[0] == "-m":
            assert importlib.util.find_spec(args[1]) is not None, line
        else:
            assert (BACKEND / args[0]).is_file(), line


@pytest.mark.parametrize("script", SHELL_SCRIPTS, ids=lambda p: p.name)
def test_every_module_a_shell_script_runs_exists(script: Path) -> None:
    targets = re.findall(r"python -m ([\w.]+)", script.read_text())
    assert targets
    for target in targets:
        assert importlib.util.find_spec(target) is not None, target
