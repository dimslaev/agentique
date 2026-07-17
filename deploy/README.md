# deploy/

Versioned copies of everything the VPS runs outside Docker. Docker only runs the db (`compose.yml` at the repo root).

Files and their install targets:

- `Caddyfile` → `/etc/caddy/Caddyfile` (TLS, static frontend, reverse proxy to the API)
- `agentique-backend.service` → `/etc/systemd/system/` (FastAPI, 4 workers, 127.0.0.1:8000)
- `agentique-pipeline.service` + `agentique-pipeline.timer` → `/etc/systemd/system/` (daily 04:00)

## Layout on the box

- `/opt/agentique` — code + `.venv` + `frontend/dist`, rsynced by the deploy workflow. Never run services out of the runner workspace (checkout resets it every run).
- `/opt/agentique/.env` — hand-written, never touched by CI. Back it up to the password manager. Must set `POSTGRES_SERVER=localhost` (the db is on `127.0.0.1:5432` now, not a Docker network). `chown ubuntu:agentique`, `chmod 640` — see below for why.

## Users and permissions

- `agentique` — dedicated user, runs both services.
- `ubuntu` — the actual self-hosted runner user on this box (the runner was registered under this account before this plan was written; there's no separate `github` user, and creating one would mean re-registering the runner for no real benefit). Owns `/opt/agentique` contents so rsync + `uv sync` work without sudo; `agentique` needs read+execute (world-readable checkout defaults are fine).
- `.env` is `ubuntu:agentique`, `640` — not `agentique:agentique 600`. The deploy job's prestart step (`uv run --env-file ../.env ...`) runs as `ubuntu`, so `ubuntu` needs read access too; `600` owned solely by `agentique` locks CI out of its own env file.
- Sudoers rule for the runner (`/etc/sudoers.d/agentique-deploy`):

```
ubuntu ALL=(root) NOPASSWD: /usr/bin/systemctl restart agentique-backend
```

## One-time setup (belongs in `.ignored/vps-setup.sh`, not committed)

Order matters: the systemd units and Caddyfile live in `deploy/`, which doesn't exist on the box until the code has been synced there once. So the first population of `/opt/agentique` is a manual `git clone` (the repo is public — no auth needed), not the CI workflow. Do the `cp` steps after that clone, not before.

This box is small (2GB RAM) — don't bring up the native stack while the old Docker stack is still running, or you'll OOM the box and lose SSH. Stop/remove the old containers before starting `agentique-backend`.

```bash
# Docker (db only, if not already present) + Caddy
# Docker: follow https://docs.docker.com/engine/install/ubuntu/ (the official repo,
# not the docker.io/docker-compose-v2 Ubuntu packages — installs a different build
# than Docker CE and wasn't the path actually used on this box).
apt-get install -y caddy

# uv — as the ubuntu user, not root, so it lands in /home/ubuntu/.local/bin
# where the runner's PATH picks it up.
curl -LsSf https://astral.sh/uv/install.sh | sh

# users + dirs
adduser --system --group agentique
mkdir -p /opt/agentique
chown ubuntu:agentique /opt/agentique

# first-ever population — after this, CI's rsync takes over
git clone https://github.com/dimslaev/agentique /opt/agentique

# .env — write by hand, then:
chown ubuntu:agentique /opt/agentique/.env && chmod 640 /opt/agentique/.env

# db, before starting the backend (prestart needs it reachable)
cd /opt/agentique && docker compose up -d
# restore the dump here if this is a fresh box, then:
cd /opt/agentique && uv sync --frozen --package app
cd /opt/agentique/backend && uv run --env-file ../.env bash scripts/prestart.sh

# stop/remove any old Docker-based app stack now, before starting units —
# see the memory note above.

# units + caddy
cp /opt/agentique/deploy/agentique-*.{service,timer} /etc/systemd/system/
cp /opt/agentique/deploy/Caddyfile /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now agentique-backend agentique-pipeline.timer
systemctl reload caddy

# sudoers (see above)
echo 'ubuntu ALL=(root) NOPASSWD: /usr/bin/systemctl restart agentique-backend' > /etc/sudoers.d/agentique-deploy
```

## Deploy flow (what CI does)

1. Build `frontend/dist` on a GitHub-hosted runner, ship it as an artifact.
2. On the self-hosted runner: checkout + download artifact, rsync to `/opt/agentique` (excluding `.env`, `.venv`, `frontend/dist`), then rsync the fresh dist.
3. `uv sync --frozen --package app`, run migrations via `uv run --env-file ../.env bash scripts/prestart.sh` (the `--env-file` is load-bearing: the production guard in prestart.sh reads the shell env).
4. `sudo systemctl restart agentique-backend`.

The pipeline needs no restart — the timer starts a fresh process each run.
