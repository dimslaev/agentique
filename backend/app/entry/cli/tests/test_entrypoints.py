"""What systemd, the deploy and prestart.sh run: that each target exists, and
the exit code each one hands back."""

from __future__ import annotations

import importlib.util
import re
import runpy
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from app.core.settings import settings
from app.entry.cli import backup_db, seed_articles, seed_stories
from app.features.collect import service as collect

BACKEND = Path(__file__).resolve().parents[4]
REPO = BACKEND.parent
SHELL_SCRIPTS = (
    BACKEND / "app/entry/cli/prestart.sh",
    REPO / "scripts/tests-start.sh",
)


def _python_targets(command: str) -> list[str]:
    """The modules a command runs with ``python -m``."""
    return re.findall(r"python -m ([\w.]+)", command)


@pytest.mark.parametrize(
    "unit", sorted((REPO / "deploy").glob("*.service")), ids=lambda p: p.name
)
def test_every_python_unit_starts_something_that_exists(unit: Path):
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
def test_every_module_a_shell_script_runs_exists(script: Path):
    targets = _python_targets(script.read_text())
    assert targets
    for target in targets:
        assert importlib.util.find_spec(target) is not None, target


@pytest.mark.parametrize(
    ("module", "verb"),
    [("app.entry.cli.collect", "run_nightly"), ("app.entry.cli.report", "send_report")],
)
@pytest.mark.parametrize("code", [0, 1])
def test_a_timer_entrypoint_exits_with_its_verbs_code(
    monkeypatch: pytest.MonkeyPatch, module: str, verb: str, code: int
):
    monkeypatch.setattr(collect, verb, lambda: code)
    with pytest.raises(SystemExit) as exited:
        runpy.run_module(module, run_name="__main__")
    assert exited.value.code == code


def test_the_backup_finds_the_compose_file():
    assert backup_db.COMPOSE_FILE == REPO / "compose.yml"
    assert backup_db.COMPOSE_FILE.is_file()


def _fake_pg_dump(monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    """Stand in for `docker compose exec db pg_dump` with a shell one-liner."""
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_DB", "app")
    real = subprocess.Popen

    def popen(_cmd: list[str], stdout: int) -> subprocess.Popen[bytes]:
        return real(["sh", "-c", script], stdout=stdout)

    monkeypatch.setattr(backup_db.subprocess, "Popen", popen)


def test_a_failed_pg_dump_fails_the_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _fake_pg_dump(monkeypatch, "echo partial; exit 3")
    with pytest.raises(RuntimeError, match="exited with 3"):
        backup_db.dump_db(tmp_path / "dump.sql.gz")


def test_a_dump_with_output_is_kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _fake_pg_dump(monkeypatch, "echo 'CREATE TABLE x ();'")
    dest = tmp_path / "dump.sql.gz"
    backup_db.dump_db(dest)
    assert dest.stat().st_size > 0


@pytest.mark.parametrize(
    "main", [seed_articles.main, seed_stories.main], ids=["articles", "stories"]
)
def test_the_seeds_refuse_production(
    monkeypatch: pytest.MonkeyPatch, main: Callable[[], None]
):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises((RuntimeError, SystemExit), match="Refusing"):
        main()
