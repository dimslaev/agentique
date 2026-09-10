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
| `sql-roles.sql` | one-time: creates the read-only and read/write login roles `agentique-sql` and the MCP server use |

## Shape

- A push to `master` triggers `.github/workflows/deploy-production.yml`: build
  the frontend on a GitHub-hosted runner, then a self-hosted runner on the box
  rsyncs the source, syncs the venv, runs migrations + prestart, and restarts
  the backend. Additive migrations only; rollback is `git revert` + push.
- The pipeline needs no restart — the timer starts a fresh process each run.
- `.github/workflows/prod-sql.yml` (`workflow_dispatch`) is break-glass writes
  only, without opening a port: the self-hosted runner pipes the statement into
  `agentique-sql`, which runs it as `agentique_rw`. Every run is an Actions
  entry with the statement, output, and who dispatched it. Reads go through the
  MCP endpoint below instead.
- Postgres is published on loopback only. `agentique_rw` is passwordless, so it
  can only be reached through the local socket (`docker exec`), never over the
  network; `agentique_ro` has a password because the backend logs in as it over
  loopback TCP for the MCP endpoint.

## MCP endpoint

`https://agentique.ch/mcp/` (note the trailing slash — `/mcp` answers with a
307). Streamable HTTP, served by the backend itself and forwarded by Caddy, so
it needs no process, port or certificate of its own.

| Tool | What it does |
| --- | --- |
| `sql_query` | read-only SQL, as `agentique_ro`, capped at 1000 rows and 10s |
| `web_fetch` | one URL to readable text, retried through the residential proxy |
| `web_search` | Tavily search |

Auth is one bearer token, `MCP_TOKEN` in `/opt/agentique/.env`. **An unset
`MCP_TOKEN` rejects every request** — the endpoint fails closed, it does not
fall open. Rotate by changing the value and restarting the backend.

One-time on the box, on top of `sql-roles.sql`: give `agentique_ro` a password
(`ALTER ROLE agentique_ro PASSWORD '<generated>';`) and put the same value in
`MCP_DB_PASSWORD`. The role is passwordless as created because
`agentique-sql` reaches it through the local socket; the backend reaches it
over TCP on loopback, which the postgres image requires a password for.

Client config lives in `.mcp.json` at the repo root and reads the token from
`AGENTIQUE_MCP_TOKEN` in the environment, so no secret is committed.

## Config

Runtime config is a single `.env` on the box, hand-written once and never
touched by CI. It must set `ENVIRONMENT=production` and
`POSTGRES_SERVER=localhost`. The MCP endpoint additionally needs `MCP_TOKEN`
and `MCP_DB_PASSWORD` (`MCP_DB_USER` already defaults to `agentique_ro`).
`.env.dev` at the repo root lists the variables with throwaway local values;
`deploy/README` in a fork should document whatever subset a given deployment
actually needs.
