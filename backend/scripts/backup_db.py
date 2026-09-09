"""Nightly Postgres backup to kDrive. Run with: python scripts/backup_db.py

pg_dump runs inside the pgvector container (`docker compose exec`) so the
client always matches the server version and nothing Postgres needs installing
on the host. The gzipped dump is uploaded to kDrive under KDRIVE_BACKUP_DIR
(kDrive auto-creates missing folders under /Private; the drive root is not
writable via the API). Uploads beyond KDRIVE_BACKUP_KEEP are pruned, oldest
first. Reads raw os.environ and loads no dotenv — systemd's EnvironmentFile
feeds it.
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from kdrive_client.kdrive_client import KDriveClient  # type: ignore[import-untyped]
from kdrive_client.kdrive_file import KDriveFile  # type: ignore[import-untyped]

COMPOSE_FILE = Path(__file__).resolve().parents[2] / "compose.yml"
BACKUP_DIR = os.environ.get("KDRIVE_BACKUP_DIR", "/Private/agentique-db")
KEEP = int(os.environ.get("KDRIVE_BACKUP_KEEP", "14"))
PREFIX = "agentique-db-"
API = "https://api.kdrive.infomaniak.com"


def dump_db(dest: Path) -> None:
    cmd = [
        "docker",
        "compose",
        "-f",
        str(COMPOSE_FILE),
        "exec",
        "-T",
        "db",
        "pg_dump",
        "-U",
        os.environ["POSTGRES_USER"],
        "--clean",
        "--if-exists",
        os.environ["POSTGRES_DB"],
    ]
    with gzip.open(dest, "wb", compresslevel=6) as out:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        assert proc.stdout is not None
        shutil.copyfileobj(proc.stdout, out)
        proc.stdout.close()
        if proc.wait() != 0:
            raise RuntimeError(f"pg_dump exited with {proc.returncode}")
    if dest.stat().st_size == 0:
        raise RuntimeError("dump is empty")


def prune(client: KDriveClient, directory_id: int) -> None:
    """Delete the oldest backups past KEEP. Timestamped names sort
    chronologically, so no reliance on server-side ordering params.

    Uses client._request: kDriveClientPY exposes no list/delete, but its
    request helper carries the auth session, rate limiter and error parsing.
    """
    if KEEP <= 0:
        return
    url = f"{API}/3/drive/{client.drive_id}/files/{directory_id}/files"
    entries = client._request("GET", url).json()["data"]
    backups = sorted(
        (e for e in entries if e["type"] == "file" and e["name"].startswith(PREFIX)),
        key=lambda e: e["name"],
    )
    for e in backups[:-KEEP]:
        client._request("DELETE", f"{API}/2/drive/{client.drive_id}/files/{e['id']}")
        print(f"pruned {e['name']}")


def main() -> None:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    with tempfile.TemporaryDirectory() as tmp:
        dump = Path(tmp) / f"{PREFIX}{stamp}.sql.gz"
        dump_db(dump)
        print(f"dumped {dump.name} ({dump.stat().st_size / 1024 / 1024:.1f} MB)")

        client = KDriveClient(
            token=os.environ["KDRIVE_API_TOKEN"],
            drive_id=int(os.environ["KDRIVE_DRIVE_ID"]),
        )
        res = client.upload(KDriveFile(str(dump)), directory_path=BACKUP_DIR)
        data = res.get("data", res)
        print(f"uploaded {data.get('name', dump.name)} to {BACKUP_DIR}")

        # Best-effort — a failed prune must not fail the backup.
        try:
            prune(client, int(data["parent_id"]))
        except Exception as e:
            print(f"prune failed (backup itself is fine): {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
