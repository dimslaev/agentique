# 23. An agent posts the day's picks to Bluesky

## Status

Accepted.

## Context

agentique.ch on Bluesky grew only when a person posted by hand. A post that
tags an article's author gets seen by that author and often reposted, but
finding the author's account takes judgment: search returns namesakes,
mirror bots and empty accounts, and tagging the wrong one notifies a
stranger.

## Decision

    curate (nightly) -> post-bluesky (daily, at lunch)
    today's approvals -> find_bluesky_account -> link_bluesky_account (saves, follows)
    top 5 -> post_bluesky, author tagged
    weekly issue live -> post_bluesky once

- **A daily routine, `post-bluesky`, at lunch,** a scheduled task like the
  others, with the write token. It posts what curation approved that
  morning, so the posts land while people are reading, not overnight.
- **Three tools.** `find_bluesky_account` lists the linked account or
  candidates, `link_bluesky_account` saves the handle as
  `publisher.links.bluesky` and follows it, `post_bluesky` posts with a link
  card and turns each `@handle` into a mention.
- **The handle lives on the publisher.** Found once, reused for every later
  article. `links` is JSON, so no migration.
- **The weekly issue is posted by the daily routine, not the newsletter
  one.** The newsletter routine opens a PR; the issue's URL works only after
  a person merges it. The daily run posts it the first day the page loads.
- **`post_bluesky` refuses a URL the account already posted,** read from its
  own last 100 posts. That makes a rerun safe and keeps the weekly step
  idempotent without a table.

## Consequences

Following a linked account adds it to the Bluesky source, so a wrong link
both tags a stranger and pulls their posts into the candidate queue. The
skill's rules for linking are the guard; a bad link is fixed by editing
`publisher.links` and unfollowing in the app.

Credentials are one app password in the server's environment
(`BLUESKY_APP_PASSWORD`). Each write logs in again, a few times a day, well
under Bluesky's session rate limit.
