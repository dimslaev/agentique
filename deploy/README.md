# deploy/

Docker runs only the db (`compose.yml` at repo root). Everything else here.

Install targets:
- `Caddyfile` → `/etc/caddy/Caddyfile`
- `agentique-backend.service` → `/etc/systemd/system/` (FastAPI, 4 workers, 127.0.0.1:8000)
- `agentique-pipeline.service` + `.timer` → `/etc/systemd/system/` (daily 04:00)
- `agentique-backup.service` + `.timer` → `/etc/systemd/system/` (daily 03:30, db dump to kDrive — needs `KDRIVE_API_TOKEN` + `KDRIVE_DRIVE_ID` in `.env`)
- `agentique-sql` → `/usr/local/bin/` (`root:root 755`, backs the Prod SQL workflow — see below)
- `sql-roles.sql` → run once against the db (creates the two login roles `agentique-sql` uses)

## Layout

- `/opt/agentique` — code + `.venv` + `frontend/dist`, rsynced by CI. Never run services out of the runner workspace (checkout resets it every run).
- `/opt/agentique/.env` — hand-written, never touched by CI. `chown ubuntu:agentique`, `chmod 640`. Restore those perms after any edit — see CLAUDE.md.
- `/var/lib/agentique` — `agentique`'s `HOME` (model2vec/huggingface cache; the user is a system account with no real home dir). `chown agentique:agentique`, `750`. Same restore-perms-after-touching gotcha as `.env`.

## Users

- `agentique` — runs both services, `HOME=/var/lib/agentique`.
- `ubuntu` — self-hosted runner user, owns `/opt/agentique`. `.env` is `ubuntu:agentique 640`, not `agentique:agentique 600` — CI's prestart step runs as `ubuntu` and needs to read it too.
- Sudoers (`/etc/sudoers.d/agentique-deploy`):

  ```
  ubuntu ALL=(root) NOPASSWD: /usr/bin/systemctl restart agentique-backend
  ubuntu ALL=(root) NOPASSWD: /usr/local/bin/agentique-sql read, /usr/local/bin/agentique-sql write
  ```

  The second rule pins both arguments, so the runner gets those two commands and nothing else.

## Remote SQL

`.github/workflows/prod-sql.yml` (`workflow_dispatch`) is how you read and update the prod db without opening a port: the runner is already on the box, so the job pipes the SQL into `sudo agentique-sql read|write`, which runs `psql` inside the `db` container. Output lands in the job log and the run summary; the Actions history is the audit trail.

- `read` → `agentique_ro`, `write` → `agentique_rw`. Roles carry their own `statement_timeout`/`lock_timeout` and the read role is forced `default_transaction_read_only` (`sql-roles.sql`).
- Write runs also need input `confirm=WRITE`, so a misclick can't mutate prod.
- All statements run in one transaction (`psql -1`) — a failure rolls the batch back, and `CREATE INDEX CONCURRENTLY`/`VACUUM` won't work. Schema changes stay in alembic.
- Both roles are passwordless and the postgres image only trusts the local socket, so they cannot log in over the ssh tunnel.
- `agentique-sql` is root-owned outside `/opt/agentique` deliberately: the runner user can rewrite everything under `/opt/agentique`, so a NOPASSWD rule pointing there would hand it root. Copy the file by hand after changing it.

For interactive poking, an ssh tunnel is still the better tool: `ssh -L 5432:localhost:5432 <vps>` and point a client at `localhost:5432` — postgres is published on loopback only, so this only works with the ssh key (see CLAUDE.md).

## One-time setup

`.ignored/vps-setup.sh` (uncommitted, box-specific). Order matters: `deploy/` only exists on the box after the first `git clone`, so units/Caddyfile get copied after that, not CI. Box has 2GB RAM — stop any old app stack before starting the native services or you'll OOM and lose SSH.

```bash
# Docker (db only, if not present) + Caddy
# Docker: https://docs.docker.com/engine/install/ubuntu/ (official repo, not
# the docker.io/docker-compose-v2 Ubuntu packages — different build)
apt-get install -y caddy

# uv — as ubuntu, not root, so it lands in /home/ubuntu/.local/bin
curl -LsSf https://astral.sh/uv/install.sh | sh

# users + dirs
adduser --system --group agentique
mkdir -p /opt/agentique /var/lib/agentique
chown ubuntu:agentique /opt/agentique
chown agentique:agentique /var/lib/agentique && chmod 750 /var/lib/agentique

# first-ever population — after this, CI's rsync takes over
# repo is private: authenticate first, e.g. an SSH deploy key or
# `gh auth login` (gh CLI rewrites the https URL transparently)
git clone https://github.com/dimslaev/agentique /opt/agentique

# .env — write by hand, then:
chown ubuntu:agentique /opt/agentique/.env && chmod 640 /opt/agentique/.env

# db, before starting the backend (prestart needs it reachable)
cd /opt/agentique && docker compose up -d
# restore a dump here if this is a fresh box, then:
cd /opt/agentique && uv sync --frozen --package app
cd /opt/agentique/backend && uv run --env-file ../.env bash scripts/prestart.sh

# stop/remove any old app stack now, before starting units — see the memory note above

# remote-sql wrapper + its roles (see "Remote SQL" above)
install -o root -g root -m 755 /opt/agentique/deploy/agentique-sql /usr/local/bin/agentique-sql
set -a; . /opt/agentique/.env; set +a
docker exec -i agentique-db-1 psql -v ON_ERROR_STOP=1 \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" < /opt/agentique/deploy/sql-roles.sql

# units + caddy
cp /opt/agentique/deploy/agentique-*.{service,timer} /etc/systemd/system/
cp /opt/agentique/deploy/Caddyfile /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now agentique-backend agentique-pipeline.timer agentique-backup.timer
systemctl reload caddy

# sudoers (see above)
echo 'ubuntu ALL=(root) NOPASSWD: /usr/bin/systemctl restart agentique-backend' > /etc/sudoers.d/agentique-deploy
```

## Deploy flow (CI)

Push to `master` → `.github/workflows/deploy-production.yml`:

1. Build `frontend/dist` on a GitHub-hosted runner, upload as artifact.
2. Self-hosted runner: rsync to `/opt/agentique` (excludes `.env`, `.venv`, `frontend/dist`), then rsync the fresh dist.
3. `uv sync --frozen --package app`, `uv run --env-file ../.env bash scripts/prestart.sh`.
4. `sudo systemctl restart agentique-backend`.

Pipeline needs no restart — the timer starts a fresh process each run. Migrate-then-restart
means additive migrations only; a few seconds of downtime per deploy is accepted. Rollback
is `git revert` + push (which redeploys) — no release directories or symlinks.

## Secrets

- GitHub side: `DOMAIN_PRODUCTION` (used for the frontend build URL), in the `production` environment.
- Box side: `/opt/agentique/.env`, hand-written once, never touched by CI. The VPS is the
  source of truth — back the file up to the password manager. It must set
  `ENVIRONMENT=production` and `POSTGRES_SERVER=localhost`.

## Self-hosted runner

A GitHub Actions runner on the VPS with labels `self-hosted` + `production`, installed as a
service ([official guide](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners)).
Runs as `ubuntu`. Needs: write access to `/opt/agentique`, uv, and the narrow sudoers rule above.

## URLs

- Frontend: `https://agentique.ch` (`www.` redirects to apex)
- API: `https://api.agentique.ch` (docs at `/docs`)
