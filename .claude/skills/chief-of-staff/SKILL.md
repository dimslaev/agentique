---
name: chief-of-staff
description: Rank the week's scout proposals by evidence and reach, write a one-screen memo with the top 3 and an argument against each, update the proposal ledger and open a GitHub issue with the memo. Use when running the Tuesday chief-of-staff session, or when asked to rank proposals, write the weekly memo or update the ledger.
---

# Chief of staff

The scouts propose, you rank. Nothing here writes to prod, builds a feature or edits a rubric. Conventions are in `docs/reports.md`.

## Tools

- git, to read the `reports` branch (`docs/reports.md`, "Reading"), and `scripts/publish-report.sh` to publish.
- GitHub MCP `issue_write`, or `gh issue create`, whichever the session has.
- No `agentique-admin` tool is needed. Call none.

## Steps

1. Fetch the `reports` branch and read `reports/ledger.md` (`docs/reports.md`, "Reading"). Today's date in Europe/Zurich is the memo's date.
2. List the reports. Read every scout and competitor report dated after the newest `chief-of-staff.md`, or all of them if there is none. That catches a scout that pushed late or a week the chief did not run.
3. Today's `mine-rejections`, `scout-archive` and `scout-revenue`, and a `watch-competitors` from the last 7 days, are expected. Note any that is missing: its run failed.
4. Collect the new proposals: the `Ledger:` lines in those reports, with the report each came from.
5. Merge duplicates: a line whose idea is already in the ledger, or appears twice among the new lines, under any id, is one proposal. Keep the first id. Add new evidence to the memo line only if it changes the rank.
6. Rank each new proposal and each earlier `proposed` one (see Ranking).
7. Write the memo and the new ledger to scratch files, e.g. `/tmp/chief-of-staff.md` and `/tmp/ledger.md`.
8. Publish both in one commit: `scripts/publish-report.sh chief-of-staff /tmp/chief-of-staff.md /tmp/ledger.md`.
9. Open the issue.

## Ranking

Score each proposal on two things and rank by the product.

- Evidence: 3 a number from the db or a cited source that a person can check, 2 a number with no source, 1 an impression. Re-check a number with a link you can open, if you can.
- Reach: 3 touches most readers or moves revenue now, 2 a segment or a small amount, 1 a handful of readers.
- Tie: the cheaper to try wins.
- Drop a proposal that scores under 4 or has no number.
- Rank only `proposed` lines. A `picked`, `dropped` or `done` line stays as it is, whoever set it.

## Memo

One screen: about 25 lines. The format of `docs/reports.md` for the title, then:

```markdown
# chief-of-staff <date>

1. <id>: <proposal>. Evidence: <number, source>. Reach: <who, how many>. Against: <one line>. Source: reports/<date>/<skill>.md
2. ...
3. ...

- Dropped: <ids and why, one line>.
- Missing: <scouts that did not report>, or leave out.
```

- The top 3 only, each with its evidence, one line arguing against it, and the report it came from, so a person finds the diff or the details there. The argument is the strongest real objection, not a hedge: cost, a cheaper fix that exists, an assumption the number rests on.
- No `Ledger:` lines in the memo. The ledger is a separate file.
- A scout report missing: say so in the memo and rank what is there.
- Fewer than 3 proposals: list what there is.

## Ledger

- Append each new proposal as `- <id> | <one line> | proposed <date>`, then change the status.
- Top 3: `picked <date>`. Ruled out: `dropped <date>`. The rest stay `proposed`.
- Never change a `picked`, `dropped` or `done` line from an earlier week.
- The script rewrites the whole file, so build the new ledger from the copy you read in step 1, changed only as above.

## Issue

- Repo `dimslaev/agentique`, title `Chief of staff <date>`.
- Body: the memo, then a link to it on the `reports` branch: `https://github.com/dimslaev/agentique/blob/reports/reports/<date>/chief-of-staff.md`.
- Open it after the push, so the link works. If the push failed, put the memo in the body anyway.
- If neither issue tool works, say so in the final message. The memo on the branch is then the only copy.

## Report

- The top 3, the issue link, what was dropped.
- Scout reports that were missing.
- Whether the push and the issue worked. A failed push: the whole memo.

Don't edit files in the repo checkout. Don't commit to master.
