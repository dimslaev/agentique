---
name: rank-proposals
description: The weekly scout run - start scout-competitors, scout-rejects and scout-growth, rank their proposals by evidence and reach, write a one-screen memo with the top 3 and an argument against each, update the ledger, publish to the proposals branch and open a GitHub issue. Use when running the Tuesday scout session, or when asked to run the scouts, rank proposals or write the weekly memo.
---

# Rank proposals

Start the scouts, then rank what they propose. Nothing here writes to prod, builds a feature or edits a rubric. Conventions are in `docs/proposals.md`.

## Tools

- The Agent tool, to run each scout in its own context.
- git, to read the `proposals` branch, and `scripts/publish-proposals.sh` to publish.
- GitHub MCP `issue_write`, or `gh issue create`, whichever the session has.
- No `agentique-admin` tool: the scouts call those.

## Steps

1. Read `proposals/ledger.md` (`docs/proposals.md`, "Reading"). Today's date in Europe/Zurich is the run's date. Make a scratch dir, e.g. `D=$(mktemp -d)`.
2. Run `scout-competitors` as a subagent. Prompt: `Run the scout-competitors skill (.claude/skills/scout-competitors/SKILL.md). The ledger: <ledger.md>. Return only the report.`
3. Run `scout-rejects` and `scout-growth` as two subagents at once, the same prompt with their own skill. Add the `scout-competitors` report to `scout-rejects`' prompt.
4. Save each report as `$D/<skill>.md`. A scout that failed or returned nothing: note it as missing and go on.
5. Collect the new proposals: the `Ledger:` lines in the reports, with the scout each came from.
6. Merge duplicates: a line whose idea is already in the ledger, or appears twice among the new lines, under any id, is one proposal. Keep the first id. Add new evidence to the memo line only if it changes the rank.
7. Rank each new proposal and each earlier `proposed` one (see Ranking).
8. Write the memo to `$D/memo.md` and the new ledger to `$D/ledger.md`.
9. Publish: `scripts/publish-proposals.sh "$D"`.
10. Open the issue.

No Agent tool: run each skill yourself in turn, in the same order, and keep only its report.

## Ranking

Score each proposal on two things and rank by the product.

- Evidence: 3 a number from the db or a cited source that a person can check, 2 a number with no source, 1 an impression. Re-check a number with a link you can open, if you can.
- Reach: 3 touches most readers or moves revenue now, 2 a segment or a small amount, 1 a handful of readers.
- Tie: the cheaper to try wins.
- Drop a proposal that scores under 4 or has no number.
- Rank only `proposed` lines. A `picked`, `dropped` or `done` line stays as it is, whoever set it.

## Memo

One screen: about 25 lines.

```markdown
# Proposals <date>

1. <id>: <proposal>. Evidence: <number, source>. Reach: <who, how many>. Against: <one line>. Details: proposals/<date>/<skill>.md
2. ...
3. ...

- Dropped: <ids and why, one line>.
- Missing: <scouts that failed>, or leave out.
```

- The top 3 only, each with its evidence, one line arguing against it, and the scout report it came from, where a person finds the diff or the details. The argument is the strongest real objection, not a hedge: cost, a cheaper fix that exists, an assumption the number rests on.
- No `Ledger:` lines in the memo.
- Fewer than 3 proposals: list what there is.

## Ledger

- Append each new proposal as `- <id> | <one line> | proposed <date>`, then change the status.
- Top 3: `picked <date>`. Ruled out: `dropped <date>`. The rest stay `proposed`.
- Never change a `picked`, `dropped` or `done` line from an earlier week.
- The script replaces the whole file, so build the new ledger from the copy you read in step 1, changed only as above.

## Issue

- Repo `dimslaev/agentique`, title `Proposals <date>`.
- Body: the memo, then a link: `https://github.com/dimslaev/agentique/blob/proposals/proposals/<date>/memo.md`.
- Open it after the push, so the link works. If the push failed, put the memo in the body anyway.
- If neither issue tool works, say so in the final message.

## Report

- The top 3, the issue link, what was dropped.
- Scouts that failed.
- Whether the push and the issue worked. A failed push: the whole memo and the new ledger.

Don't edit files in the repo checkout. Don't commit to master.
