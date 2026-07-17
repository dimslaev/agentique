# deploy/

Versioned copies of everything the VPS runs outside Docker. Docker only runs the db (`compose.yml` at the repo root).

Files and their install targets:

- `Caddyfile` → `/etc/caddy/Caddyfile` (TLS, static frontend, reverse proxy to the API)
- `agentique-backend.service` → `/etc/systemd/system/` (FastAPI, 4 workers, 127.0.0.1:8000)
- `agentique-pipeline.service` + `agentique-pipeline.timer` → `/etc/systemd/system/` (daily 04:00)

## Layout on the box

- `/opt/agentique` — code + `.venv` + `frontend/dist`, rsynced by the deploy workflow. Never run services out of the runner workspace (checkout resets it every run).
- `/opt/agentique/.env` — hand-written, never touched by CI. Back it up to the password manager. Must set `POSTGRES_SERVER=localhost` (the db is on `127.0.0.1:5432` now, not a Docker network). Readable by the `agentique` user only (`chmod 600`).

## Users and permissions

- `agentique` — dedicated user, runs both services.
- `github` — the self-hosted runner user. Owns `/opt/agentique` contents so rsync + `uv sync` work without sudo; `agentique` needs read+execute (world-readable checkout defaults are fine).
- Sudoers rule for the runner (`/etc/sudoers.d/agentique-deploy`):

```
github ALL=(root) NOPASSWD: /usr/bin/systemctl restart agentique-backend
```

## One-time setup (belongs in `.ignored/vps-setup.sh`, not committed)

```bash
# Docker (db only) + uv + Caddy
apt-get install -y docker.io docker-compose-v2 caddy
curl -LsSf https://astral.sh/uv/install.sh | sh   # as the github user

# users + dirs
adduser --system --group agentique
mkdir -p /opt/agentique
chown github:agentique /opt/agentique

# .env — write by hand, then:
chown agentique:agentique /opt/agentique/.env && chmod 600 /opt/agentique/.env

# units + caddy
cp /opt/agentique/deploy/agentique-*.{service,timer} /etc/systemd/system/
cp /opt/agentique/deploy/Caddyfile /etc/caddy/Caddyfile
systemctl daemon-reload
systemctl enable --now agentique-backend agentique-pipeline.timer
systemctl reload caddy

# sudoers (see above)
echo 'github ALL=(root) NOPASSWD: /usr/bin/systemctl restart agentique-backend' > /etc/sudoers.d/agentique-deploy
```

The db: `cd /opt/agentique && docker compose up -d` (reads `.env` for POSTGRES_*).

## Deploy flow (what CI does)

1. Build `frontend/dist` on a GitHub-hosted runner, ship it as an artifact.
2. On the self-hosted runner: checkout + download artifact, rsync to `/opt/agentique` (excluding `.env`, `.venv`, `frontend/dist`), then rsync the fresh dist.
3. `uv sync --frozen --package app`, run migrations via `uv run --env-file ../.env bash scripts/prestart.sh` (the `--env-file` is load-bearing: the production guard in prestart.sh reads the shell env).
4. `sudo systemctl restart agentique-backend`.

The pipeline needs no restart — the timer starts a fresh process each run.
