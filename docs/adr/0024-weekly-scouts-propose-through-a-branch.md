# 24. Weekly scouts propose through a branch

## Status

Accepted.

## Context

The curation, newsletter, stories, discovery and Bluesky routines (ADRs 9, 12,
16, 21, 23) run the archive and publish it. None of them asks what to build
next: what competitors do better, what the rejects say readers could want,
where readers or revenue could come from. Those jobs end in ideas, not rows,
and a person has to choose among them.

Run weekly, the same scouts would propose the same ideas again unless something
remembers what was already proposed, picked or turned down.

## Decision

    Tue 16:00  rank-proposals
                 -> scout-competitors
                 -> scout-rejects, scout-growth
                 -> memo, ledger, GitHub issue

- **One session.** `rank-proposals` starts the three scouts as subagents, so
  each gets a fresh context, then ranks what they return. One schedule, one
  writer, no handoff between runs.
- **Every scout is read-only.** The competitors are nightly sources (AINews
  through the Latent Space feed, AI/TLDR by mail, Aligned News by RSS), so a
  story they ran that we never saw is a source gap to fix, not a link to queue
  by hand. No session that reads outside pages holds the write token.
- **An orphan branch, `proposals`.** Each run writes one report per scout and a
  memo under `proposals/<date>/`. `proposals/ledger.md` lists every proposal
  and its status. Convention in `docs/proposals.md`.
- **The ranker argues.** Evidence (a number or a source) times reach (readers
  or revenue). The memo is one screen: the top 3, each with one line against
  it. It is also opened as a GitHub issue, so GitHub emails it.
- **Nothing builds, posts or edits automatically.** No scout builds a feature,
  posts anywhere, or edits the curation rubric. A person acts on a pick.

## Why not a table or issues alone

- A db table needs a migration and an MCP tool for what is a handful of text
  lines a week, and puts agent notes into the schema prod runs on.
- Issues alone give no cheap read-before-propose, and every proposal would
  notify. One memo issue a week keeps the email useful.
- Files in master would put weekly agent output into the code history and
  trigger a deploy on every push.

## Consequences

- A proposal costs one line in a file. A failed scout is named in the memo and
  the rest is ranked.
- If the session cannot run `gh` or the GitHub issue tool, the memo on the
  branch is the only copy, and nobody gets an email.
- A person's ledger edit pushed during the run makes the publish fail rather
  than drop either change.
- Ranking is the session's judgment on thin numbers. Treat the order as a
  suggestion, and read the line against each pick.
