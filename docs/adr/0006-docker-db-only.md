# 6. Docker for the pgvector database only

## Status

Accepted.

## Context

The upstream template's Compose stack ran everything in containers:
backend, frontend, a mail-catcher, a reverse proxy, and the database.
Running a single VPS with that much container overhead, for a project at
agentique's current scale, added operational weight (image builds, network
config, log plumbing) without a matching benefit — the backend and
pipeline are single Python processes with no need for container isolation
from each other, and the frontend is static files.

## Decision

Docker runs exactly one thing: `db` (`ghcr.io/dimslaev/pgvector:pg17`),
bound to `127.0.0.1:5432` so only the local machine can reach it
(`compose.yml`). Everything else is native:

- backend — FastAPI via a uv-managed venv, `agentique-backend.service`
  (systemd), 4 workers, reverse-proxied by Caddy.
- pipeline — the same uv venv, `agentique-pipeline.service` +
  `.timer` (systemd), daily 04:00.
- frontend — built to static files (`bun run build`), served directly by
  Caddy.

Local development mirrors this: `docker compose up -d` starts only the db;
backend and frontend run natively via `uv run fastapi dev` and `bun run
dev`.

## Consequences

One container to reason about instead of a whole stack; `deploy/README.md`
documents the systemd units and Caddy config as the real deployment
surface instead of a Compose file. This is also why `pipeline.run` and the
`app` uv package name are frozen (see the screaming-architecture plan) —
systemd units reference them directly, with no container layer to absorb a
rename.
