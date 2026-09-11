# deploy/

How agentique runs in production. Docker runs only the database
(`compose.yml` at the repo root); everything else is native.

## Pieces

| File | Role |
| --- | --- |
| `Caddyfile` | TLS + static frontend + reverse proxy to the API (`/etc/caddy/Caddyfile`) |
| `agentique-backend.service` | FastAPI under systemd, 2 workers, bound to `127.0.0.1:8000` |
| `agentique-pipeline.service` + `.timer` | the article pipeline, one run daily at 04:00 |
| `agentique-backup.service` + `.timer` | nightly DB dump to off-box storage at 03:30 |
| `agentique-sql` | run SQL against the prod DB from stdin, inside the `db` container |
| `sql-roles.sql` | one-time: creates the read-only and read/write login roles `agentique-sql` uses |

## Shape

- A push to `master` triggers `.github/workflows/deploy-production.yml`: build
  the frontend on a GitHub-hosted runner, then a self-hosted runner on the box
  rsyncs the source, syncs the venv, runs migrations + prestart, and restarts
  the backend. Additive migrations only; rollback is `git revert` + push.
- The pipeline needs no restart — the timer starts a fresh process each run.
- Break-glass writes are `agentique-sql` over ssh, run by hand: it pipes the
  statement into `psql` as `agentique_rw`, with that role's statement, lock and
  idle timeouts. There is no CI path for it — prefer a migration, and reach for
  this only when nothing else will fix prod.
- Postgres is published on loopback only. `agentique_rw` is passwordless, so it
  can only ever be reached through the local socket (`docker exec`), never over
  the network. `agentique_ro` has a password so it can also be used over
  loopback TCP; it is SELECT-only, read-only by default, and cannot see the
  `user` table at all.

## Config

Runtime config is a single `.env` on the box, hand-written once and never
touched by CI. It must set `ENVIRONMENT=production` and
`POSTGRES_SERVER=localhost`. `.env.dev` at the repo root lists the variables
with throwaway local values; `deploy/README` in a fork should document whatever
subset a given deployment actually needs.
