#!/usr/bin/env bash
# Start the local pgvector container and restore the newest dump in dumps/.
# Destructive by design: the dumps are `pg_dump --clean --if-exists`, so every
# run drops and recreates the objects in $POSTGRES_DB.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  cp .env.dev .env
  echo "no .env found — copied .env.dev"
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

dump=$(ls -1 dumps/agentique-db-*.sql.gz 2>/dev/null | sort | tail -1)
if [ -z "$dump" ]; then
  echo "no dump in dumps/ — drop a dump in dumps/ or run backend/scripts/seed_articles.py" >&2
  exit 1
fi

docker compose up -d db

for _ in $(seq 1 60); do
  if docker compose exec -T db pg_isready -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"; then
    break
  fi
  sleep 2
done

echo "restoring $dump into $POSTGRES_DB"
gzip -dc "$dump" \
  | docker compose exec -T db psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"

docker compose exec -T db psql -tA -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "select relname || ' ' || n_live_tup from pg_stat_user_tables order by relname;"
echo "done — connect with postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB"
