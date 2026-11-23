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

## Ledger format

One line per proposal, newest last:

```markdown
- <id> | <one line> | <status> <YYYY-MM-DD>
```

- Status is `proposed`, `picked`, `dropped` or `done`. The date is when it
  last changed.
- `chief-of-staff` adds each week's new lines as `proposed`, then marks the
  top 3 `picked` and the rest it ruled out `dropped`. A person marks `done`.

## Publishing

Run from the repo checkout. `<skill>` is the routine's skill name.

```bash
D=$(TZ=Europe/Zurich date +%F)
R=$(mktemp -d)
git fetch origin reports
git worktree add --detach "$R" FETCH_HEAD
```

Read `$R/reports/ledger.md`, write `$R/reports/$D/<skill>.md`, then:

```bash
git -C "$R" add reports
git -C "$R" commit -m "docs: <skill> report $D"
for i in 1 2 3 4; do
  git -C "$R" push origin HEAD:reports && break
  sleep $((i * 5))
  git -C "$R" pull --rebase origin reports
done
```

- Routines that run at the same time write different files, so a rebase never
  conflicts.
- A push that still fails: put the whole report in the session's final message
  and say the push failed. Don't retry further.

## Creating the branch

Once, by hand, before the first routine runs:

```bash
git switch --orphan reports
mkdir -p reports && printf '# Ledger\n' > reports/ledger.md
git add reports && git commit -m "docs: start reports ledger"
git push -u origin reports
git switch master
```
