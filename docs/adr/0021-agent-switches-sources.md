# 21. An agent switches publishers on and off

## Status

Accepted.

## Context

HN and the newsletters find new sites, and the pipeline makes each one an
inactive publisher it never polls (ADR 13). On 2026-11-21 prod had 390
inactive publishers with 1 or 2 approvals in 90 days and 13 with 3 or more,
and nobody reviewed them. Active feeds went the other way: 29 of 95 RSS
feeds and 20 of 41 Substacks had no approval in 90 days, and nothing
switched them off. The table could not tell a publisher never polled from
one a person had switched off.

## Decision

    curate (nightly) -> discover (daily, after curate)
    discovery_candidates -> cull rows  -> disable_publisher
                         -> probe rows -> find_feed -> read posts
                                       -> activate_publisher | disable_publisher

- **A daily agent, `discover`, switches publishers.** It reads a site's
  newest posts against the curate rubric and turns it on at 3 passes, a 40%
  pass rate over everything judged, and a post in the last 90 days. It
  never publishes: curate stays the only judge of articles (ADR 9).
- **Code holds the limits.** `discovery_candidates` leaves out shared
  hosts, publishers a probe cannot lift to 40%, and publishers with a
  standing `disabled_reason`. `activate_publisher` re-reads the feed and
  refuses a dead one. The skill cannot switch on what the code rules out.
- **Culling is arithmetic.** An active feed is switched off at 0 approvals
  in 10 or more decisions over 90 days, or 120 days with no new candidate
  since its last new one or since it was switched on.
- **Two new columns on `publisher`.** `disabled_reason` says why it is off.
  `switched_at` is when the agent last switched it. A publisher the agent
  switched off comes back only on an approval after `switched_at`. One a
  person switched off has no `switched_at` and stays off; the migration
  marks every inactive publisher that already had a feed or search link
  that way.

## Consequences

- Sources grow from what readers approve, with no hand-picked list.
- A bad activation costs at most a few nights of queued noise before the
  cull catches it.
- To turn a hand-disabled publisher back on, a person clears
  `disabled_reason` or switches it on directly.
- Medium writers are left out with the other shared-host accounts, though
  their feeds would work.
