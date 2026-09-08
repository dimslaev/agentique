#!/usr/bin/env bash
# Fail if any tracked file is a utils/helpers/common/shared/misc grab bag.
# frontend/src/lib/utils.ts is grandfathered - shadcn convention, see ADR 3.
set -euo pipefail
banned='(^|/)(utils|helpers|common|shared|misc)\.(py|ts|tsx)$'
matches=$(git ls-files | grep -E "$banned" | grep -v '^frontend/src/lib/utils\.ts$' || true)
if [ -n "$matches" ]; then
  echo "Banned grab-bag module name(s) - see docs/adr/0003-no-utils-module.md:" >&2
  echo "$matches" >&2
  exit 1
fi
