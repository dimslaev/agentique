# dumps

`scripts/restore-db.sh` restores the newest `agentique-db-*.sql.gz` in this
folder into a local Docker Postgres. The dumps themselves are gitignored
(`dumps/*.sql.gz`) — this directory is just the agreed drop point.

To get data into a fresh checkout, either:

- run `backend/scripts/seed_articles.py` for synthetic demo data, or
- drop your own `pg_dump --clean --if-exists` gzip here, named
  `agentique-db-<UTC timestamp>.sql.gz`, then run `scripts/restore-db.sh`.

Local DB credentials come from `.env.dev` (throwaway values, copied to `.env`
when missing). `POSTGRES_USER` must stay `postgres` — the dumps carry
`OWNER TO postgres`. Restoring is destructive and idempotent: `--clean` drops
existing objects first, so re-running is safe.
