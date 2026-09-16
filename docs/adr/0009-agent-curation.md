# 9. An agent curates, the pipeline only collects

## Status

Accepted.

## Context

The pipeline scored every candidate 1-100 with an LLM against the rubric in
`baml_src/score.baml` and inserted what cleared a threshold. On 2026-09-16, 70
articles from six months of the feed were hand-labelled — 27 love, 22 fine, 21
noise — and the deployed rubric was run over them.

| | result |
|---|---|
| noise kept | 11 of 21 |
| loved dropped | 13 of 27 |
| mean score, loved vs noise | 65.7 vs 65.6 |

Wrong in both directions, and with no separating power at all: the two
populations the scorer exists to separate had the same mean. Worse, the same
prompt over the same input three times gave a per-item spread with a median of 7
and a maximum of 48. A threshold tuned against a judge that swings 40 points on
identical input means nothing.

Two things were tried before this. Rewriting the rubric (40 lines instead of 75,
every lesson from the labelling folded in) halved the noise kept — 6 of 21 — and
did not move the loved side at all: 12 of 26 still dropped. Deterministic URL
rules (`pipeline/limits.py`, written, measured, reverted) removed 8 of 21 noise
for free, but only reached structural cases — a `/pricing` path, a help-centre
host. Neither touched the actual failure.

The failure is that the judge never read the article. It saw a title, a 200-char
snippet and a trust tag, and from that it was asked to tell a practitioner
write-up with real measurements from a landing page quoting the same numbers.
Those two look identical at 200 characters. They do not look remotely alike on
the page.

## Decision

Delete the judge from the pipeline. The nightly run fetches, filters and stops:

    pipeline:  fetch -> regex gate -> known/dead/thin -> dedup -> queue as candidate
    agent:     read candidates -> fetch the page -> approve or reject
    approve:   summary + tags + embedding written, the article goes live

A Claude Code session runs an hour after the pipeline, reads the candidates
through four MCP tools (`list_candidates`, `get_content`, `approve`, `reject`),
and decides each one. It can fetch the page, compare a claim against the repo it
points at, and check the last few days of the feed for the same story told
again. Its rubric lives in `.claude/skills/curate/SKILL.md`, in prose, next to
the regression set it was measured against.

Three things follow from the shape:

**Candidates reuse the reject ledger.** A new `RejectStage.pending` rather than a
table of its own: the row already holds title, source, publisher, content,
traction and dates, and `filter_known_urls` already reads the table, so a
candidate waiting for a verdict is not re-fetched the next night. No `article`
row exists until approval, so nothing half-published is ever visible, and a
reject keeps the agent's score and reason in the same column the scorer's went.

**Two tokens on the MCP server.** `MCP_TOKEN` reaches the three reading tools.
`MCP_WRITE_TOKEN` carries the scope that `approve` and `reject` demand.
`sql_query` stays read-only, on its own SELECT-only role.

**The report moved.** The run lands nothing now, so a report at 04:00 would be a
page of counts an hour before the articles exist. `pipeline.report` sends the
night's one email at 06:00, after the agent: what landed, named one by one, and
what did not as a count and the loudest few publishers. A crash still emails
immediately.

## Consequences

The pipeline makes no LLM call at all. Scoring, summarizing and enrichment were
three calls per article on everything that survived filtering; they are now one
session over the survivors, and the summary is written by something that read
the page rather than a 12000-character prefix of it.

Nothing is dropped when the agent does not run. Candidates stay pending and the
next session reads them alongside the new ones, so a missed night is a late feed
rather than a lost one. The failure mode is visible: the 06:00 report says
nothing landed and names the size of the queue.

Every verdict is kept with a reason written for a human. Ten likes is all the
signal the app has produced so far; a season of agent verdicts is the next
labelled set, and the thing that would let neighbour scoring on embeddings work.

The cost is a second scheduled thing that can break, and a judge whose
consistency is unmeasured over time rather than measured and bad. The rubric is
pinned against `.claude/skills/curate/regression.md` before it runs unattended —
noise kept under 3 of 21, loved dropped under 3 of 27 — and the verdicts
accumulate for the next check.

`steps/score.py` stays reachable behind `LLM_SCORING=1` until the agent has run
clean for a week. Then it goes, and `score.baml`, `SCORE_THRESHOLD` and
`CURATED_INDIVIDUAL_THRESHOLD` go with it.
