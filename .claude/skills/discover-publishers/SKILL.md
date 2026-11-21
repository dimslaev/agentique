---
name: discover-publishers
description: Find the sites agentique should poll and switch off the feeds it shouldn't - probe inactive publishers that have earned approvals, read their recent posts against the `curate-articles` rubric, activate the ones that pass, and deactivate active feeds that stopped earning approvals. Use when running the daily discovery session, or when asked to find new sources, activate publishers or deactivate feeds.
---

# Discover sources

Decide which inactive publishers to start polling and which feeds to stop. You never publish.

## Tools

`agentique-admin` MCP: `review_publishers`, `find_feed`, `activate_publisher`, `deactivate_publisher`, `web_fetch`, `web_search`.

## Steps

1. Call `review_publishers()` once.
2. Deactivate every `deactivate` row with its `reason` as given.
3. Probe each `probe` row in order.

## Probing

1. Find the feed: `find_feed(website)`, then its blog page (`/blog`, `/posts`, `/news`), then one web search for `<site> rss feed`.
2. It must be the publisher's own posts. Not comments, changelogs, podcasts, jobs, docs or status. A wrong feed is no feed.
3. No post in 90 days: deactivate as dead, read nothing.
4. Prior approvals are passes, prior `below_threshold` rejections are fails. Read only entries with `judged` "".
5. Fail funding, hiring, event and off-topic posts on the title alone.
6. Read the rest newest first and judge each.
7. Stop once settled:
   - activate at 3+ passes and 40%+ pass rate
   - deactivate once that's out of reach

Every probed publisher ends in one activate or deactivate call.

## The bar

- A post passes at 70+ under the `curate-articles` rubric, without its tie-breaks, caps or publisher count.
- Judge the usual post, not the best one. One great post among nine launch notes is 1/10.
- Releases from the creator count. Marketing pages and case studies fail.

## No feed

- Lab or company: read its blog page and judge the same way. If it passes, activate with `search_domain` set to its host.
- Anyone else: deactivate with "no feed".

## Reasons

The numbers, the deciding fact, today's date:

- `"probe 3/4 + prior 2/2 = 5/6, AI eval write-ups 2026-11-21"`
- `"dead feed, newest 2026-05-02 2026-11-21"`
- `"no feed 2026-11-21"`
- `"wrong feed: comments only 2026-11-21"`

## Report

- activated: slug, feed or search, numbers
- deactivated: slug and reason
- posts read, fetches and searches
- tool errors

Don't edit files or commit. If `review_publishers` is missing or says "Authorization failed", stop and say so.
