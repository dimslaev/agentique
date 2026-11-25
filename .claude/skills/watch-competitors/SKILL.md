---
name: watch-competitors
description: Compare last week's top stories at AINews, Aligned News and AI/TLDR with ours: how far ahead or behind we were, why we rejected what we did. Queue what we never saw, add the publishers we don't know, and report the features they have that we don't. Use when running the Friday competitor session, or when asked to watch, diff or benchmark competitors.
---

# Watch competitors

Diff the competitors' last week against ours. You queue and add; curation judges. You never build anything.

## Tools

`agentique-admin` MCP: `sql_query` (reads `article`, `scored_url` and `publisher`), `web_fetch`, `web_search`, `find_feed`, `activate_publisher`, and the two writes `add_publisher(url, reason)` and `queue_candidate(url, reason)`.

## Read each competitor

Last 7 days. Per story keep: title, URL it links to, their date. Top stories only, about 15 per competitor.

- AINews: `https://news.smol.ai/issues` lists the daily issues, newest first (the same list is at `latent.space/news`). `web_fetch` each issue from the last 7 days. The stories are its own bold headlines with links; skip the Discord and Twitter recaps.
- Aligned News: `https://alignednews.com/ai` is rendered in the browser and `web_fetch` returns nothing for it. Read its feed instead: `sql_query "select links::text from publisher where slug = 'aligned-news'"`, then `web_fetch` the `rss` link. Its items are mostly tweets; the tweet's linked page is the story. Skip events.
- AI/TLDR: `https://ai-tldr.dev/ai/archives`, not the landing page. Entries are release cards, "Name - what happened", with a source link; some are YouTube videos and funding news. `web_fetch` returns the text without dates or links: look each title up with `web_search` for the source URL and date. No date found: leave `seen_at` null. The story still counts in the match, never in `hours_ahead` or `Ahead:`.

A site that fails twice: say so in the report and go on. Never invent a story.

## Match

Our table is `article`, our time is `created_at`. Their time is theirs. Run it per competitor, with its stories in `t`. Match by URL, then by title:

```sql
with t(url, title, seen_at) as (values
  ('https://example.com/post', 'Their title', '2026-11-20 09:00+00'::timestamptz))
select distinct on (t.url) t.url, t.title, a.url as our_url, a.created_at as ours_at,
  round(extract(epoch from t.seen_at - a.created_at) / 3600) as hours_ahead,
  r.stage, r.reason, r.detail::text as detail
from t
left join article a on rtrim(a.url, '/') = rtrim(t.url, '/') or lower(a.title) = lower(t.title)
left join scored_url r on rtrim(r.url, '/') = rtrim(t.url, '/') or lower(r.title) = lower(t.title)
order by t.url, (rtrim(a.url, '/') = rtrim(t.url, '/')) desc nulls last,
  (rtrim(r.url, '/') = rtrim(t.url, '/')) desc nulls last
```

One row per story, a URL match before a title match.

- `our_url` set: ours. `hours_ahead` is positive when we published first, negative when they did.
- `stage` `below_threshold`: rejected, `reason` says why. Other stages (`prefilter`, `duplicate`, `thin_repo`, `unusable_summary`): rejected, read `detail`. Don't re-queue.
- `stage` `pending`: queued already, wait for curation.
- No row: we never saw it. Check its publisher:

```sql
select slug, is_active, type from publisher where links::text ilike '%example.com%'
```

## Act

1. Never seen: `queue_candidate(url, reason)`. Reason: competitor, date, where it ran, e.g. `"AINews 2026-11-20, lead story"`. It credits the publisher, making an inactive one for a site we don't know, and its reply names the publisher and whether it is polled. A refusal ("already known", "No readable text", "event or reference page", "star floor", "names no publisher") is the answer: note it, move on.
2. A queued story whose publisher is inactive and looks like a regular source: `find_feed`, then `activate_publisher` only if it passes `discover-publishers`: follow its "Probing" and "The bar". A publisher that fails stays inactive.
3. `add_publisher(url, reason)` only for a story `queue_candidate` refused for its page ("No readable text", "No title found") whose site still looks worth polling. Then probe it as in step 2.
4. At most 10 `queue_candidate` calls a run, the ones that look most like our archive. Count the rest in the report.

## Features

Open each competitor's site as a reader. Name one feature it has that we lack (filters, digests by topic, search, alerts, a tracker, an API). Max one per competitor, none if nothing stands out. Read `reports/ledger.md` first (`docs/reports.md`, "Reading") and skip an idea already there. Each is a proposal: a ledger id, what it is, why readers would use it. Build nothing.

## Report

Per `docs/reports.md`: at most 5 bullets, each ending in a proposal or a number. Write it to `/tmp/watch-competitors.md`, then `scripts/publish-report.sh watch-competitors /tmp/watch-competitors.md`.

- One bullet starts `Ahead:`. Our biggest leads among dated stories, up to 3, each as `URL +Nh (competitor)`. No lead: `Ahead: none this week`.
- One bullet for where we were behind (count, largest gap) and what we rejected (count, most common reason, any we think were wrong).
- One bullet for what you queued and added: counts, publishers added, activated.
- One `Features:` bullet with every proposal, each with its ledger id. Then the `Ledger:` lines.

If a tool errors or a site was unreadable, name it in the last bullet. Don't edit files in the repo or commit to master.
