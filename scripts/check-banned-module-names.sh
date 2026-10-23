#!/usr/bin/env bash
# Fail if any tracked file is a utils/helpers/common/shared/misc grab bag, or
# lives in a folder by one of those names - a folder full of small files says
# no more about what it holds than the one module did.
# frontend/src/shared/lib/utils.ts is grandfathered - shadcn convention, see ADR 3.
# frontend/src/shared/ is FSD's bottom layer, a name Steiger needs - see ADR 3.
# This script still checks the rest of each path below it.
set -euo pipefail

cd "$(dirname "$0")/.."

banned_module='(^|/)(utils|helpers|common|shared|misc)\.(py|ts|tsx)$'
banned_dir='(^|/)(utils|helpers|common|shared|misc)/'
layer='frontend/src/shared/'
matches=$(git ls-files | while IFS= read -r path; do
  rest=${path#"$layer"}
  if [[ $rest =~ $banned_module || $rest =~ $banned_dir ]] \
    && [ "$path" != frontend/src/shared/lib/utils.ts ]; then
    echo "$path"
  fi
done)
if [ -n "$matches" ]; then
  echo "Banned grab-bag module or folder name(s) - see docs/adr/0003-no-utils-module.md:" >&2
  echo "$matches" >&2
  exit 1
fi
