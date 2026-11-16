#!/usr/bin/env bash
# Judge and insert the tools in a GitHub search list, one batch per model call.
# Each call starts empty: no tools, no settings, no session. A judged repo is
# known to the db, so stopping and re-running picks up where it left off.
#
#   scripts/backfill-tools.sh .ignored/backfill/tools.json [batch size] [max batches]
#
# With BACKFILL_SSH=agentique-prod the db steps run on that host against its
# db, and only the model call runs here.
set -euo pipefail

tools=$(realpath "$1")
size=${2:-30}
max=${3:-1000}
work=$(mktemp -d)
cd "$(dirname "$0")/../backend"

if [ -n "${BACKFILL_SSH:-}" ]; then
  scp -q "$tools" "$BACKFILL_SSH:/tmp/backfill-tools.json"
  tools=/tmp/backfill-tools.json
  cli() {
    ssh "$BACKFILL_SSH" "cd /opt/agentique/backend && set -a && . ../.env && set +a \
      && ../.venv/bin/python -m app.entry.cli.backfill_tools $*"
  }
else
  cli() { uv run python -m app.entry.cli.backfill_tools "$@"; }
fi

for i in $(seq 1 "$max"); do
  cli next "$tools" -n "$size" > "$work/batch.txt" 2>/dev/null
  [ -s "$work/batch.txt" ] || { echo "no tools left"; break; }
  # Run from the empty work dir so no CLAUDE.md is picked up.
  (cd "$work" && claude -p --model sonnet --tools "" --strict-mcp-config \
    --disable-slash-commands --setting-sources "" --no-session-persistence \
    --system-prompt "You output JSONL only. No prose, no code fences." \
    < batch.txt > "verdicts-$i.jsonl")
  if [ -n "${BACKFILL_SSH:-}" ]; then
    scp -q "$work/verdicts-$i.jsonl" "$BACKFILL_SSH:/tmp/backfill-verdicts.jsonl"
    verdicts=/tmp/backfill-verdicts.jsonl
  else
    verdicts="$work/verdicts-$i.jsonl"
  fi
  echo "batch $i: $(cli apply "$tools" "$verdicts" 2>/dev/null | tail -1)"
done
echo "verdict files kept in $work"
