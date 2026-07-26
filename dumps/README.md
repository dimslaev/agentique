# dumps

Gzipped `pg_dump` snapshot of the prod database, named
`agentique-db-<UTC timestamp>.sql.gz`. Only the latest snapshot is kept in the
working tree — older ones stay in git history.

Restore into a local/sandbox db (also used by cloud sessions):

```bash
scripts/restore-db.sh
```

That script copies `.env.dev` to `.env` when `.env` is missing, starts the
`db` service from `compose.yml`, and restores the newest dump in this folder.
Connection string it prints:

```
postgresql://postgres:agentique-dev@localhost:5432/app
```

Credentials live in committed `.env.dev` — throwaway values for a local db
only. `POSTGRES_USER` must stay `postgres`, since the dumps carry
`OWNER TO postgres`.

Refresh from prod (needs the `agentique-prod` ssh alias, so local only):

```bash
scripts/dump-prod-db.sh
```

It writes a new timestamped dump, deletes the older ones from the working
tree, and leaves the result to be committed.

Notes:

- The dumps are `--clean --if-exists`, so restoring drops existing objects
  first. Re-running is safe and idempotent.
- Full data dumps: `user`, `newsletter_subscriber` and `analytics_event`
  tables are included. Repo is private; keep it that way.
- Nightly off-repo backups still go to kDrive via `backend/scripts/backup_db.py`.
