# 23. Scouts propose through a reports branch

## Status

Accepted.

## Context

The curation, newsletter, stories and discovery routines (ADRs 9, 16, 21) all
work on the archive itself. Nothing looks outward: at what competitors ship, at
what the rejects say readers could want, at where revenue could come from, at
how to reach readers. Those jobs end in ideas, not rows, and a person has to
choose among them.

Run weekly, the same scouts would propose the same ideas again unless something
remembers what was already proposed, picked or turned down.

## Decision

    Fri 16:00  watch-competitors
    Tue 16:00  mine-rejections, scout-archive, scout-revenue, draft-distribution
    Tue 17:00  chief-of-staff -> memo, ledger, GitHub issue

- **An orphan branch, `reports`.** Each run writes
  `reports/<date>/<skill>.md`. `reports/ledger.md` lists every proposal and its
  status. The branch shares no history with master and is never merged.
  Convention in `docs/reports.md`.
- **Only the chief of staff writes the ledger.** Scouts read it before they
  propose and put new ideas in their report as `Ledger:` lines. The chief adds
  them, marks the top 3 `picked` and the ones it rules out `dropped`. One
  writer means parallel scouts never conflict on it, and ids stay unique. A
  person marks `done`.
- **The chief ranks and argues.** Evidence (a number or a source) times reach
  (readers or revenue). The memo is one screen: the top 3, each with one line
  against it. It is also opened as a GitHub issue, so GitHub emails it.
- **Only `watch-competitors` writes to prod**, and only publishers and pending
  candidates, the two things the nightly run and the curation agent already
  handle. The other routines are read-only.
- **Nothing builds, posts or edits automatically.** No routine builds a feature
  from a proposal, posts to Bluesky or Hacker News, or edits the curation
  rubric (`.claude/skills/curate-articles/SKILL.md`). A person acts on a
  picked proposal.

## Why not a table or issues alone

- A db table needs a migration and an MCP tool for what is a handful of text
  lines a week, and puts agent notes into the schema prod runs on.
- Issues alone give no cheap read-before-propose: a scout would search them
  and miss near-duplicates, and every proposal would notify. One memo issue a
  week keeps the email useful.
- Files in master would put weekly agent output into the code history and
  trigger a deploy on every push. A separate branch keeps master for code.

## Consequences

- A proposal costs one line in a file. Nothing is lost when a scout fails:
  the memo names the missing report and ranks the rest.
- If the scheduled sessions cannot run `gh` or the GitHub issue tool, the memo
  on the branch is the only copy, and nobody gets an email.
- The ledger has no lock. A rebase conflict needs two sessions editing the
  same file, which the layout avoids.
- Ranking is the chief's judgment on thin numbers. Treat the order as a
  suggestion, and read the line against each pick.
