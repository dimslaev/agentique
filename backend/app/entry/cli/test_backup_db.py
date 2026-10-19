"""The nightly database backup: where it finds compose, and what it refuses to keep."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.entry.cli import backup_db

REPO = Path(__file__).resolve().parents[4]


def test_the_backup_finds_the_compose_file() -> None:
    assert backup_db.COMPOSE_FILE == REPO / "compose.yml"
    assert backup_db.COMPOSE_FILE.is_file()


def _fake_pg_dump(monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    """Stand in for `docker compose exec db pg_dump` with a shell one-liner."""
    monkeypatch.setenv("POSTGRES_USER", "postgres")
    monkeypatch.setenv("POSTGRES_DB", "app")
    real = subprocess.Popen

    def popen(_cmd: list[str], stdout: int) -> subprocess.Popen[bytes]:
        return real(["sh", "-c", script], stdout=stdout)

    monkeypatch.setattr(subprocess, "Popen", popen)


def test_a_failed_pg_dump_fails_the_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_pg_dump(monkeypatch, "echo partial; exit 3")
    with pytest.raises(RuntimeError, match="exited with 3"):
        backup_db.dump_db(tmp_path / "dump.sql.gz")


def test_an_empty_dump_fails_the_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_pg_dump(monkeypatch, "true")
    with pytest.raises(RuntimeError, match="empty"):
        backup_db.dump_db(tmp_path / "dump.sql.gz")


def test_a_dump_with_output_is_kept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_pg_dump(monkeypatch, "echo 'CREATE TABLE x ();'")
    dest = tmp_path / "dump.sql.gz"
    backup_db.dump_db(dest)
    assert dest.stat().st_size > 0
