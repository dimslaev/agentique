# Proposals

Where the weekly scouts write. They propose, a person decides. Nothing here
reaches prod or master. Decision in ADR 24.

## The run

One scheduled session, Tuesday 16:00 Europe/Zurich, runs `rank-proposals`:

1. It reads the ledger.
2. It starts `scout-competitors`, then `scout-rejects` (with the competitor
   findings) and `scout-growth` at once, each as a subagent with the ledger.
3. It ranks their proposals, writes the memo and the new ledger, publishes
   them in one commit and opens a GitHub issue with the memo.

Every scout is read-only and runs on the read token.

## Layout

- Orphan branch `proposals`. It shares no history with master and is never
  merged.
- `proposals/<YYYY-MM-DD>/<skill>.md`: one report per scout per run, and
  `memo.md`. The date is the run's date in Europe/Zurich.
- `proposals/ledger.md`: every proposal ever made and where it stands.

## Report format

The same for every scout:

```markdown
# <skill> <YYYY-MM-DD>

- At most 5 bullets. Each ends in a proposal or a number.

Ledger:
- <id> | <one line> | proposed
```

- `<id>` is a short kebab slug that names the idea, such as `per-tag-digest`.
  It must not already be in the ledger.
- An idea already in the ledger under another id is not new. Skip it, or cite
  its id if there is new evidence for it.
- A run with nothing worth proposing still returns its report, with no
  `Ledger:` lines.
- One section may follow the `Ledger:` lines, `## Details`, for what a person
  needs to act on a proposal and that doesn't fit a bullet: rubric diffs,
  query output.

## Ledger format

One line per proposal, newest last:

```markdown
- <id> | <one line> | <status> <YYYY-MM-DD>
```

- Status is `proposed`, `picked`, `dropped` or `done`. The date is when it
  last changed.
- `rank-proposals` adds each week's new lines as `proposed`, marks the top 3
  `picked` and the ones it rules out `dropped`. A proposal it neither picks
  nor drops stays `proposed` and is ranked again next week.
- A person marks `done`, or changes any status, by editing the line on the
  branch. Avoid Tuesday 16:00 to 17:00 Europe/Zurich: an edit pushed during
  the run can conflict, and the run then fails to publish.

## Reading

```bash
git fetch -q origin +proposals:refs/remotes/origin/proposals
git show origin/proposals:proposals/ledger.md
git ls-tree -r --name-only origin/proposals proposals/
```

## Publishing

`scripts/publish-proposals.sh <dir>` from the repo checkout. `<dir>/ledger.md`
replaces the ledger, every other `<dir>/*.md` goes to `proposals/<today>/`, in
one commit. A non-zero exit means nothing was published: put the memo and the
ledger in the session's final message.

## Creating the branch

Once, before the first run. Skip it if `git ls-remote origin proposals` prints
a ref:

```bash
T=$(mktemp -d)
git worktree add --detach "$T" HEAD
cd "$T"
git switch --orphan proposals
mkdir -p proposals && printf '# Ledger\n' > proposals/ledger.md
git add proposals && git commit -m "docs: start proposals ledger"
git push -u origin proposals
cd - && git worktree remove --force "$T"
```
