# 24. Scouts propose through a reports branch

## Status

Accepted.

## Context

The curation, newsletter, stories, discovery and Bluesky routines (ADRs 9, 12,
16, 21, 23) run the archive and publish it. None of them asks what to build
next: what competitors ship, what the rejects say readers could want, where
revenue could come from. Those jobs end in ideas, not rows, and a person has to
choose among them.

Run weekly, the same scouts would propose the same ideas again unless something
remembers what was already proposed, picked or turned down.

## Decision

    Fri 16:00  watch-competitors
    Tue 16:00  mine-rejections, scout-archive, scout-revenue
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
- **Only `watch-competitors` writes to prod**, and only what the nightly run
  already writes: inactive publishers, `pending` candidates and the
  `thin_repo` rows its filter records. It switches a publisher on only when it
  passes the `discover-publishers` bar. The other routines only read, and need
  only the read token's tools.
- **Nothing builds, posts or edits automatically.** None of these routines
  builds a feature from a proposal, posts anywhere, or edits the curation
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
  same file, which the layout avoids; `scripts/publish-report.sh` fails rather
  than drop a commit when it happens. A person's edit to the ledger during the
  chief's run can be overwritten.
- Ranking is the chief's judgment on thin numbers. Treat the order as a
  suggestion, and read the line against each pick.
