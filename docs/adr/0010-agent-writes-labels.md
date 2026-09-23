# 10. The curation agent writes the labels, and reads from the db

## Status

Accepted.

## Context

After 0009 the agent read each article and wrote its summary, and approving it
then did two more things. It fetched the page again, because the pending row
kept only the first 2000 characters. And it ran `CategorizeAndTag`, a second
model reading 1500 characters of an article the agent had just read in full.

The agent also fetched most pages itself, because 2000 characters is too
little to judge an article by. So one article could be fetched three times in
one night: by the pipeline, by the agent, and again on approval.

## Decision

- A pending candidate keeps up to 12000 characters (`rejects.CANDIDATE_CAP`).
  The pipeline has already extracted the full text, so storing more costs no
  extra fetch. Rejecting a candidate trims its text back to 2000 characters
  (`rejects.CONTENT_CAP`), so only the queue waiting for a verdict is large.
- `get_content` is where the agent reads the article. `web_fetch` on the
  candidate's own URL is for text that is missing, a teaser, or cut off.
- `approve` takes `categories`, `kind` and `tags` from the agent, checked
  against the `vocabulary` tool. A github, huggingface or arxiv URL still sets
  its own kind. Approving makes no LLM call and no fetch. The embedding is the
  only enrichment left.
- The skill says when to use web search: to find out who an unknown publisher
  is, to check that the evidence an article points at exists, to find the
  original of a retelling, and to look up a name newer than the model's
  training data.

## Consequences

Approving is one insert plus a local embedding. `CategorizeAndTag` runs only on
the `LLM_SCORING=1` path and goes when that path goes.

A night's pending rows can hold up to 12 KB of text each. They drop back to
2 KB when rejected and move to `article` when approved.

Labels are now part of the verdict, so the regression set checks them along
with the scores the next time it runs.
