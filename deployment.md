# Deployment

One VPS. Docker runs only the database; everything else is native:

- `db` — Docker container (`ghcr.io/dimslaev/pgvector:pg17`), published on `127.0.0.1:5432`
- `caddy` — apt package + systemd; TLS, serves `frontend/dist`, reverse-proxies `api.` to the backend
- `agentique-backend.service` — FastAPI via uv venv, 4 workers, `127.0.0.1:8000`
- `agentique-pipeline.service` + `.timer` — daily at 04:00

Everything lives in `/opt/agentique`. The unit files and Caddyfile are versioned in [`deploy/`](./deploy/README.md), which also documents the one-time VPS setup, the user/permission model, and the sudoers rule.

## How a deploy works

Push to `master` → `.github/workflows/deploy-production.yml` builds the frontend on a GitHub-hosted runner, then the self-hosted runner on the VPS syncs it to `/opt/agentique`, runs migrations, and restarts the backend. Full step-by-step in [`deploy/README.md`](./deploy/README.md#deploy-flow-what-ci-does).

Notes:

- Migrate-then-restart: additive migrations only; a few seconds of downtime per deploy is accepted.
- Rollback = `git revert` + push (which redeploys). No release directories or symlinks.
- The pipeline picks up new code automatically — the timer starts a fresh process each run.

## Secrets

- GitHub side: just `DOMAIN_PRODUCTION` (used for the frontend build URL), in the `production` environment.
- Box side: `/opt/agentique/.env`, hand-written once, never touched by CI. The VPS is the source of truth — back the file up to the password manager. It must set `ENVIRONMENT=production` and `POSTGRES_SERVER=localhost`.

## Self-hosted runner

A GitHub Actions runner on the VPS with labels `self-hosted` + `production`, installed as a service ([official guide](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners)). Runs as whichever user the runner was registered under (see `deploy/README.md` for the current one — don't duplicate it here, it's the kind of detail that drifts). The runner only needs: write access to `/opt/agentique`, uv, and the narrow sudoers rule from `deploy/README.md`.

## Database

```bash
cd /opt/agentique && docker compose up -d
```

- The volume is `agentique_app-db-data`. Never run `docker compose down -v` on prod — `-v` deletes it.
- Postgres is published on loopback only. For remote inspection, tunnel: `ssh -L 5432:localhost:5432 <vps>` and point a client at `localhost:5432`.
- Backups: `docker compose exec db pg_dump -U <user> <db> > dump.sql`, copy it off the box.

## URLs

- Frontend: `https://agentique.ch` (`www.` redirects to apex)
- API: `https://api.agentique.ch` (docs at `/docs`)
