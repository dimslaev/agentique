#!/usr/bin/env bash
# Publish a business routine's report to the `reports` branch (docs/reports.md).
#
#   scripts/publish-report.sh <skill> <report.md> [<ledger.md>]
#
# Copies the report to reports/<today in Europe/Zurich>/<skill>.md, and the
# ledger to reports/ledger.md when given, in a throwaway worktree, then pushes
# with up to 4 retries. One command, so nothing depends on shell state carried
# between an agent's Bash calls. Exits non-zero if the push never lands; a
# rebase conflict (someone edited the same file meanwhile) counts as a failure,
# never as a silent drop.
set -euo pipefail

skill=${1:?usage: publish-report.sh <skill> <report.md> [<ledger.md>]}
report=${2:?usage: publish-report.sh <skill> <report.md> [<ledger.md>]}
ledger=${3:-}
day=$(TZ=Europe/Zurich date +%F)
tree=$(mktemp -d)
trap 'git worktree remove --force "$tree" 2>/dev/null || rm -rf "$tree"' EXIT

git fetch -q origin +reports:refs/remotes/origin/reports
git worktree add -q --detach "$tree" origin/reports
mkdir -p "$tree/reports/$day"
cp "$report" "$tree/reports/$day/$skill.md"
if [ -n "$ledger" ]; then
	cp "$ledger" "$tree/reports/ledger.md"
fi
git -C "$tree" add reports
git -C "$tree" commit -q -m "docs: $skill report $day"

for attempt in 1 2 3 4; do
	if git -C "$tree" push -q origin HEAD:reports; then
		echo "Published reports/$day/$skill.md"
		exit 0
	fi
	sleep $((attempt * 5))
	git -C "$tree" fetch -q origin reports
	if ! git -C "$tree" rebase -q FETCH_HEAD; then
		git -C "$tree" rebase --abort
		break
	fi
done
echo "Push to reports failed. Put the whole report in the final message." >&2
exit 1
