"""What the deploy ships: the workflow's rsync run against this checkout's
tracked files, then every path the units and the deploy job use looked up in
the result."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3]
REPO = BACKEND.parent
BOX = Path("/opt/agentique")
UNITS = sorted((REPO / "deploy").glob("*.service"))
WORKFLOW = REPO / ".github/workflows/deploy-production.yml"
# Never shipped: the box keeps its own copy, and the filter protects it.
BOX_OWNED = (BOX / ".env", BOX / ".venv")


def rsync_command() -> list[str]:
    lines = [
        line.strip()
        for line in WORKFLOW.read_text().splitlines()
        if line.strip().startswith("rsync ")
    ]
    assert len(lines) == 1, lines
    return shlex.split(lines[0])


@pytest.fixture(scope="module")
def shipped(tmp_path_factory: pytest.TempPathFactory) -> Path:
    version = subprocess.run(
        ["rsync", "--version"], capture_output=True, text=True, check=False
    ).stdout
    if "version 3." not in version:
        pytest.skip("the filter needs rsync 3, as on the box")
    # The deploy syncs a clean checkout, so untracked files must not count.
    source = tmp_path_factory.mktemp("checkout")
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True
    ).stdout.decode()
    for name in filter(None, tracked.split("\0")):
        if (REPO / name).is_file():
            (source / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / name, source / name)
    (source / "frontend/dist").mkdir(parents=True)
    (source / "frontend/dist/index.html").touch()

    dest = tmp_path_factory.mktemp("box")
    command = rsync_command()
    assert command[-1] == f"{BOX}/", command
    subprocess.run([*command[:-1], f"{dest}/"], cwd=source, check=True)
    return dest


def on_box(shipped: Path, path: Path) -> Path:
    return shipped / path.relative_to(BOX)


def box_owned(path: Path) -> bool:
    return any(path == owned or owned in path.parents for owned in BOX_OWNED)


@pytest.mark.parametrize("unit", UNITS, ids=lambda p: p.name)
def test_every_path_a_unit_uses_is_shipped(shipped: Path, unit: Path) -> None:
    config = dict(
        line.split("=", 1)
        for line in unit.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    workdir = on_box(shipped, Path(config["WorkingDirectory"]))
    assert workdir.is_dir(), workdir
    assert box_owned(Path(config["EnvironmentFile"]))
    # systemd's -, @, + and ! prefixes change how it runs, not what.
    command, *args = config["ExecStart"].lstrip("-@+!:").split()
    assert box_owned(Path(command)), command
    if args[:1] == ["-m"]:
        module = workdir / args[1].replace(".", "/")
        assert module.with_suffix(".py").is_file() or (module / "__main__.py").is_file()
    for arg in args:
        if arg.endswith(".py"):
            assert (workdir / arg).is_file(), arg


def test_every_directory_the_deploy_job_works_in_is_shipped(shipped: Path) -> None:
    dirs = re.findall(r"working-directory: (/opt/agentique\S*)", WORKFLOW.read_text())
    assert dirs
    for workdir in dirs:
        assert on_box(shipped, Path(workdir)).is_dir(), workdir
    for script in re.findall(r"bash (\S+\.sh)", WORKFLOW.read_text()):
        assert (on_box(shipped, BOX / "backend") / script).is_file(), script


def test_prestart_runs_only_shipped_modules(shipped: Path) -> None:
    prestart = shipped / "backend/app/entry/cli/prestart.sh"
    for module in re.findall(r"python -m ([\w.]+)", prestart.read_text()):
        assert (shipped / "backend" / (module.replace(".", "/") + ".py")).is_file()


def test_uv_sync_and_alembic_find_their_files(shipped: Path) -> None:
    root = tomllib.loads((shipped / "pyproject.toml").read_text())
    for member in root["tool"]["uv"]["workspace"]["members"]:
        assert (shipped / member / "pyproject.toml").is_file(), member
    assert (shipped / "uv.lock").is_file()
    assert (shipped / ".python-version").is_file()
    assert (shipped / "backend/migrations/env.py").is_file()
    # backup_db.py runs docker compose against the repo root's compose.yml.
    assert (shipped / "compose.yml").is_file()


def test_every_data_file_in_app_is_shipped(shipped: Path) -> None:
    data = [
        p.relative_to(REPO)
        for p in (BACKEND / "app").rglob("*")
        if p.is_file()
        and p.suffix not in {".py", ".pyc"}
        and not p.name.startswith("test_")
    ]
    assert data
    for path in data:
        assert (shipped / path).is_file(), path


def test_no_test_code_is_shipped(shipped: Path) -> None:
    names = {p.name for p in (shipped / "backend").rglob("*.py")}
    assert not [n for n in names if n.startswith("test_")]
    assert "conftest.py" not in names
    assert "factories.py" not in names


def test_every_shipped_module_imports_from_the_shipped_tree(shipped: Path) -> None:
    # Run from the shipped backend/, as the units do. The venv's editable
    # install still points at the checkout, so a module the filter drops would
    # load from there instead. Fail on any module that did.
    env_file = REPO / ".env"
    if env_file.is_file():
        shutil.copy(env_file, shipped / ".env")
    script = f"""
import importlib, pkgutil, sys
import app
for module in pkgutil.walk_packages(app.__path__, "app."):
    importlib.import_module(module.name)
checkout = [
    name for name, module in sys.modules.items()
    if (getattr(module, "__file__", None) or "").startswith({f"{BACKEND}/"!r})
]
assert not checkout, checkout
"""
    subprocess.run([sys.executable, "-c", script], cwd=shipped / "backend", check=True)
