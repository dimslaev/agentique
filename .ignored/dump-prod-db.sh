#!/usr/bin/env bash
# Take a fresh prod dump into dumps/ and drop the older ones from the working
# tree, so dumps/ always holds exactly the latest snapshot (git history keeps
# the rest). Needs the `agentique-prod` ssh alias — does not work from a cloud
# session, which has no ssh access to the server.
set -euo pipefail

cd "$(dirname "$0")/.."

stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="dumps/agentique-db-$stamp.sql.gz"
remote="/tmp/agentique-db-$stamp.sql.gz"

# pg_dump runs inside the container so client and server versions always match.
ssh agentique-prod "set -a; . /opt/agentique/.env; set +a; \
  sudo docker exec agentique-db-1 pg_dump -U \"\$POSTGRES_USER\" --clean --if-exists \"\$POSTGRES_DB\" \
  | gzip -6 > $remote"

mkdir -p dumps
scp -q "agentique-prod:$remote" "$out"
ssh agentique-prod "rm -f $remote"

if [ ! -s "$out" ]; then
  echo "dump is empty" >&2
  rm -f "$out"
  exit 1
fi

find dumps -name 'agentique-db-*.sql.gz' ! -name "$(basename "$out")" -delete
ls -lh "$out"
