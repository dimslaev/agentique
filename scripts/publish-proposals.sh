#!/usr/bin/env bash
# Publish one weekly scout run to the `proposals` branch (docs/proposals.md).
#
#   scripts/publish-proposals.sh <dir>
#
# <dir>/ledger.md replaces proposals/ledger.md; every other <dir>/*.md goes to
# proposals/<today in Europe/Zurich>/. One commit, made in a throwaway worktree
# so the checkout stays as it is. Exits non-zero if the push fails, including a
# rebase conflict with a ledger edit pushed during the run.
set -euo pipefail

dir=${1:?usage: publish-proposals.sh <dir>}
day=$(TZ=Europe/Zurich date +%F)
tree=$(mktemp -d)
trap 'git worktree remove --force "$tree" 2>/dev/null || rm -rf "$tree"' EXIT

git fetch -q origin +proposals:refs/remotes/origin/proposals
git worktree add -q --detach "$tree" origin/proposals
mkdir -p "$tree/proposals/$day"
for f in "$dir"/*.md; do
	if [ "$(basename "$f")" = ledger.md ]; then
		cp "$f" "$tree/proposals/ledger.md"
	else
		cp "$f" "$tree/proposals/$day/"
	fi
done
git -C "$tree" add proposals
git -C "$tree" commit -q -m "docs: proposals $day"

# The run is the only writer; one retry covers a person's edit meanwhile.
if ! git -C "$tree" push -q origin HEAD:proposals; then
	git -C "$tree" pull -q --rebase origin proposals
	git -C "$tree" push -q origin HEAD:proposals
fi
echo "Published proposals/$day"
