#!/usr/bin/env bash
# Fail if any tracked file is a utils/helpers/common/shared/misc grab bag, or
# lives in a folder by one of those names - a folder full of small files says
# no more about what it holds than the one module did.
# frontend/src/lib/utils.ts is grandfathered - shadcn convention, see ADR 3.
set -euo pipefail
banned_module='(^|/)(utils|helpers|common|shared|misc)\.(py|ts|tsx)$'
banned_dir='(^|/)(utils|helpers|common|shared|misc)/'
matches=$(git ls-files | grep -E "$banned_module|$banned_dir" | grep -v '^frontend/src/lib/utils\.ts$' || true)
if [ -n "$matches" ]; then
  echo "Banned grab-bag module or folder name(s) - see docs/adr/0003-no-utils-module.md:" >&2
  echo "$matches" >&2
  exit 1
fi
