# 11. The pipeline collects and forgets nothing; the agent judges

## Status

Accepted.

## Context

After 0009 and 0010 the curation agent was the only judge, but the pipeline
still judged in front of it. A title regex dropped off-topic posts from gated
feeds, a DNS lookup dropped dead domains, a star count dropped thin repos, and
an embedding comparison dropped anything within 0.30 of an article the feed
carried. The LLM scoring path sat behind `LLM_SCORING=1`, unused. Two sources,
Reddit and AI News, had fetched nothing all week.

Two agent-only nights (2026-09-22 and 09-23) put numbers on the gates: 273
fetched, 145 known URLs, 12 dropped by the topic regex, 2 by dedup, none by the
thin-repo or dead-domain checks, 114 queued. The gates were saving about 7
candidates a night, and each one was a verdict the agent never saw and nobody
could audit. Dedup in particular threw away the fact that several outlets had
carried a story, which is the most direct reach evidence there is.

The agent's context was the other problem. The 2026-09-23 session, whose
routine said to fetch the page first, peaked at 313k tokens over 98 candidates.
76% of the tool text was `web_fetch`, 45 of its 47 calls on the candidate's own
URL at about 8.4k characters each: the text `get_content` already held. Once
the agent reads through `get_content` instead, the 12k-character pages become
the bulk, so reading less of each one is the lever.

## Decision

    sources -> extract text + links -> drop known URLs -> queue -> agent -> embed

- **The pipeline collects.** The topic, DNS, stars and dedup gates are gone.
  The known-URL check stays: it is what stops a URL being judged twice.
  Hacker News keeps its own keyword gate, because its firehose is mostly not
  about AI and that gate runs before anything is fetched.
- **Extraction keeps what it used to throw away.** Tables stay in the text, and
  the links the article body makes are grouped (repo, model, paper, docs) and
  stored on the candidate (`scored_url.links`).
- **The agent reads less and compares more.** `get_content` pages, 4000
  characters at a time, with the links on page one: a reject can stop there, an
  approval reads on. `stories` groups the queue with itself and the feed once a
  night; `similar` puts one candidate beside the feed and the ledger before an
  approval, and counts `coverage`, the distinct publishers carrying the story.
  `check_link` answers stars, last push, README and weights for a repo or model
  without a fetch. `reject_many` settles triage in one call.
- **Coverage is reach evidence, like traction.** High coverage with no primary
  article in the feed means approving the best first-party item and rejecting
  the copies as retellings.
- **A publisher's record replaces its trust tag.** `list_candidates` shows the
  publisher's approvals over decisions in the last 90 days. The hand-set
  `trust` and `topic_gated` columns are no longer read, and stay.
- **Health lives on the publisher.** `last_fetched_at`, `last_new_at` and
  `last_error` are written after each run. `pipeline_run` keeps ok, duration
  and per-source `{fetched, queued, error}`. The daily mail is built by query:
  a crashed or stale run, sources that fetched nothing, publishers whose last
  fetch failed, and what got published. Publisher silence is left out of it.
- **The LLM scoring path, Reddit and AI News are deleted.**

## Consequences

The pipeline makes one judgement, "seen this URL before", and it is the only
one nobody needs to audit. Everything else the agent decides, with its reason
on the row. About 7 more candidates reach it a night.

Every copy of a story now reaches the agent, and it has to pick one. That is
more reading, which paging, `stories` and `similar` exist to pay for. The
number to watch is peak context against the 313k baseline, measured the same
way (tool-result characters per tool in the session jsonl).

`similar` and `stories` embed ledger rows on the fly in the API process, about
500 a week with model2vec, already loaded there. If the ledger grows past that
by an order of magnitude, the vectors belong on the row.

`check_link` is unauthenticated against GitHub (60 requests an hour), which a
night's approvals fit inside. A failed lookup reads "unknown", never zero, so
a rate limit cannot look like an unused repo.

The rubric changed with the tools. It goes back on the schedule only after the
regression set, with its new coverage cases, clears the same bar as before.

Every migration is additive (`scored_url.links`, three publisher columns), so
any single commit reverts cleanly.
