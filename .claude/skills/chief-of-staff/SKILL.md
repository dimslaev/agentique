---
name: chief-of-staff
description: Rank the week's scout proposals by evidence and reach, write a one-screen memo with the top 3 and an argument against each, update the proposal ledger and open a GitHub issue with the memo. Use when running the Tuesday chief-of-staff session, or when asked to rank proposals, write the weekly memo or update the ledger.
---

# Chief of staff

The scouts propose, you rank. Nothing here writes to prod, builds a feature or edits a rubric. Conventions are in `docs/reports.md`.

## Tools

- git, for the `reports` branch (commands in `docs/reports.md`, "Publishing").
- GitHub MCP `issue_write`, or `gh issue create`, whichever the session has.
- No `agentique-admin` tool is needed. Call none.

## Steps

1. Set up the worktree as in `docs/reports.md`, "Publishing". `D` is today in Europe/Zurich.
2. Read `reports/ledger.md`.
3. Read `reports/$D/` for `mine-rejections.md`, `scout-archive.md`, `scout-revenue.md`, `draft-distribution.md`, and the newest `reports/*/watch-competitors.md` (Friday's). Note any that is missing: its run failed.
4. Collect the new proposals: the `Ledger:` lines in the scout reports and the competitor report. `draft-distribution` holds drafts, not proposals. Skip it here and link it in the memo.
5. Drop a line whose idea is already in the ledger under another id. Add its new evidence to the old id's memo line only if it changes the rank.
6. Rank each new proposal and each earlier `proposed` one (see Ranking).
7. Write the memo, `reports/$D/chief-of-staff.md`.
8. Update `reports/ledger.md`, in the same commit as the memo.
9. Publish as in `docs/reports.md`. Commit subject: `docs: chief-of-staff report $D`.
10. Open the issue.

## Ranking

Score each proposal on two things and rank by the product.

- Evidence: 3 a number from the db or a cited source that a person can check, 2 a number with no source, 1 an impression. Re-check a number with a link you can open, if you can.
- Reach: 3 touches most readers or moves revenue now, 2 a segment or a small amount, 1 a handful of readers.
- Tie: the cheaper to try wins.
- Drop a proposal that scores under 4, has no number, or the ledger shows a person dropped before.

## Memo

One screen: about 25 lines. The format of `docs/reports.md` for the title, then:

```markdown
# chief-of-staff <date>

- 1. <id>: <proposal>. Evidence: <number, source>. Reach: <who, how many>. Against: <one line>.
- 2. ...
- 3. ...
- Dropped: <ids and why, one line>.
- Missing: <scouts that did not report>, or leave out.
- Drafts: reports/<date>/draft-distribution.md


```

- The top 3 only, each with its evidence and one line arguing against it. The argument is the strongest real objection, not a hedge: cost, a cheaper fix that exists, an assumption the number rests on.
- No `Ledger:` lines in the memo. The ledger is a separate file.
- A scout report missing: say so in the memo and rank what is there.
- Fewer than 3 proposals: list what there is.

## Ledger

- Append each new proposal as `- <id> | <one line> | proposed <date>`, then change the status.
- Top 3: `picked <date>`. Ruled out: `dropped <date>`. The rest stay `proposed`.
- Never change a line a person has set to `done` or `dropped` earlier.

## Issue

- Repo `dimslaev/agentique`, title `Chief of staff <date>`.
- Body: the memo, then a link to it on the `reports` branch: `https://github.com/dimslaev/agentique/blob/reports/reports/<date>/chief-of-staff.md`.
- Open it after the push, so the link works. If the push failed, put the memo in the body anyway.
- If neither issue tool works, say so in the final message. The memo on the branch is then the only copy.

## Report

- The top 3, the issue link, what was dropped.
- Scout reports that were missing.
- Whether the push and the issue worked. A failed push: the whole memo.

Don't edit files outside the `reports` worktree. Don't commit to master.
