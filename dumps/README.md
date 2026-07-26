# dumps

Point-in-time `pg_dump` snapshots of the prod database, gzipped.
Naming: `agentique-db-<UTC timestamp>.sql.gz`.

Created with (on prod, from `/opt/agentique`):

```bash
set -a; . /opt/agentique/.env; set +a
sudo docker exec agentique-db-1 pg_dump -U "$POSTGRES_USER" --clean --if-exists "$POSTGRES_DB" \
  | gzip -6 > /tmp/agentique-db.sql.gz
```

Restore into a local db:

```bash
gzip -dc dumps/agentique-db-<stamp>.sql.gz \
  | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

The dump carries `--clean --if-exists`, so restoring drops the existing objects first.

Nightly off-repo backups go to kDrive via `backend/scripts/backup_db.py`.

Note: these are full data dumps — they include the `user`, `newsletter_subscriber`
and `analytics_event` tables.
