# Reports

Where the business routines write. They propose, a person decides. Nothing here
reaches prod or master.

## Layout

- Orphan branch `reports`. It shares no history with master and is never merged.
- `reports/<YYYY-MM-DD>/<skill>.md`: one report per routine per run. The date
  is the run's date in Europe/Zurich.
- `reports/ledger.md`: every proposal ever made and where it stands. Only
  `chief-of-staff` writes it. Everyone else reads it before proposing, so
  nothing is proposed twice.

## Report format

The same for every routine:

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
- A run with nothing worth proposing still writes its report, with no
  `Ledger:` lines.
- `Ledger:` lists only the ideas new this run.
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
- `chief-of-staff` adds each week's new lines as `proposed`, then marks the
  top 3 `picked` and the rest it ruled out `dropped`. A proposal it neither
  picks nor drops stays `proposed` and is ranked again next week. A person
  marks `done`, or changes any status by editing the line.
- `chief-of-staff` rewrites the whole file, so edit it outside its run
  (Tuesday 17:00 to 17:30 Europe/Zurich), or the edit may be lost.
- `chief-of-staff` also writes `reports/<date>/chief-of-staff.md`, the memo.
  It is not a scout report and has no `Ledger:` lines.

## Reading

Fetch the branch into its own ref, then read from that ref. Each line works
on its own, so it holds across separate Bash calls:

```bash
git fetch -q origin +reports:refs/remotes/origin/reports
git show origin/reports:reports/ledger.md
git ls-tree -r --name-only origin/reports reports/
git show origin/reports:reports/<YYYY-MM-DD>/<skill>.md
```

## Publishing

Write the report to a scratch file, then run one command from the repo
checkout:

```bash
scripts/publish-report.sh <skill> /tmp/<skill>.md
```

- It copies the file to `reports/<today>/<skill>.md` in a throwaway worktree,
  commits `docs: <skill> report <today>`, and pushes, retrying 4 times with a
  rebase between tries.
- `chief-of-staff` passes the new ledger as a third argument; the script
  writes it to `reports/ledger.md` in the same commit.
- Routines that run at the same time write different files, so a rebase only
  conflicts when two runs wrote the same file. The script then stops and fails
  instead of dropping a commit.
- A non-zero exit: put the whole report in the session's final message and say
  the push failed. Don't retry further.

## Creating the branch

Once, before the first routine runs. Skip it if `git ls-remote origin reports`
prints a ref. Use a temporary worktree so your checkout stays as it is:

```bash
T=$(mktemp -d)
git worktree add --detach "$T" HEAD
cd "$T"
git switch --orphan reports
mkdir -p reports && printf '# Ledger\n' > reports/ledger.md
git add reports && git commit -m "docs: start reports ledger"
git push -u origin reports
cd - && git worktree remove --force "$T"
```
