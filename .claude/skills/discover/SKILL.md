---
name: discover
description: Find the sites agentique should poll and switch off the feeds it shouldn't - probe inactive publishers that have earned approvals, read their recent posts against the curate rubric, activate the ones that pass, and cull active feeds that stopped earning approvals. Use when running the daily discovery session, or when asked to find new sources, activate publishers or cull feeds.
---

# Discover sources

You decide which inactive publishers the pipeline should start polling, and
which polled feeds it should stop. You never publish: the posts you read only
decide the switch. Curate judges them once the feed is on.

## Tools

From the `agentique-admin` MCP server: `discovery_candidates`, `find_feed`,
`activate_publisher`, `disable_publisher`, `web_fetch`, and `web_search` only
to find a feed `find_feed` missed. Each tool's description says what it
returns.

## Rounds

1. `discovery_candidates()` once.
2. **Cull.** `disable_publisher(slug, reason)` for every `cull` row, with its
   `reason` as given.
3. **Probe** each `probe` row in order, as below.
4. **Report.** See **Finish**.

## Probing one publisher

1. **Find the feed.** `find_feed(website)`. If it fails, `find_feed` the blog
   page the site links to (`/blog`, `/posts`, `/news`). Then one `web_search`
   for `<site> rss feed`. Still nothing: see **No feed**.
2. **Check it is the publisher's own posts.** Not comments, a release
   changelog, a podcast, job ads, docs or status. A wrong feed counts as no
   feed.
3. **Check it is alive.** No entry in 90 days: disable as a dead feed, read
   nothing.
4. **Count what is decided.** Prior approvals are passes, prior
   `below_threshold` rejections are fails. Read only entries with `judged` "".
5. **Triage on title** as curate round 1 does. A funding note, hiring post,
   event recap or off-topic post fails unread.
6. **Read the rest** with `web_fetch`, newest first, and judge each against
   **The bar**.
7. **Stop once settled.**
   - Activate at 3+ passes with a pass rate of 40%+ over everything judged.
   - Disable once 3 passes or 40% is out of reach, even if every unread post
     passed.

Every probed publisher ends in exactly one `activate_publisher` or
`disable_publisher` call.

## The bar

A post passes when it would score **70 or above** under the curate rubric
(`.claude/skills/curate/SKILL.md`, **The rubric**). Apply it in full, except
the tie-breaks, daily caps and coverage.

- **Judge the site's usual post, not its best.** One great write-up among
  nine launch notes is 1/10. A polled feed puts every post in front of
  curate.
- **First-party releases count** at the score curate would give them.
  Marketing pages, case studies and customer stories fail.

## No feed

- **Lab or company:** read its blog or news page with `web_fetch` and judge
  the posts the same way. If it passes, activate with `search_domain` set to
  its website host.
- **Anyone else:** disable with "no feed".

## Verdicts

`reason`: the numbers, the one fact that decided it, today's date.

- `"probe 3/4 + prior 2/2 = 5/6, AI eval write-ups 2026-11-21"`
- `"probe 1/5 + prior 1/1 = 2/6, mostly product launch notes 2026-11-21"`
- `"dead feed, newest 2026-05-02 2026-11-21"`
- `"no feed 2026-11-21"`
- `"wrong feed: comments only 2026-11-21"`

## Finish

Report, short:

- activated: slug, feed or search, the numbers
- culled: slug and reason
- disabled after probe: slug and reason
- posts read, fetches and searches made
- anything a tool refused

Do not edit files or commit. If `discovery_candidates` is missing or answers
"Authorization failed", the session has the read token: stop and say so.
