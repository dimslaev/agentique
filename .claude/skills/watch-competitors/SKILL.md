---
name: watch-competitors
description: Compare last week's top stories at AINews, Aligned News and AI/TLDR with ours - how far ahead or behind we were, why we rejected what we did, queue what we never saw, add the publishers we don't know - and report the features they have that we don't. Use when running the Friday competitor session, or when asked to watch, diff or benchmark competitors.
---

# Watch competitors

Diff the competitors' last week against ours. You queue and add; curation judges. You never build anything.

## Tools

`agentique-admin` MCP: `sql_query` (write token, so `scored_url` and `publisher` are readable), `web_fetch`, `web_search`, `find_feed`, `activate_publisher`, and the two writes `add_publisher(url, reason)` and `queue_candidate(url, reason)`.

## Read each competitor

Last 7 days. Per story keep: title, URL it links to, their date. Top stories only, about 15 per competitor.

- AINews: `https://news.smol.ai/issues` lists the daily issues, newest first (the same list is at `latent.space/news`). `web_fetch` each issue from the last 7 days. The stories are its own bold headlines with links; skip the Discord and Twitter recaps.
- Aligned News: `https://alignednews.com/ai` is rendered in the browser and `web_fetch` returns nothing for it. Read its feed instead: `sql_query "select links::text from publisher where slug = 'aligned-news'"`, then `web_fetch` the `rss` link. Its items are mostly tweets; the tweet's linked page is the story. Skip events.
- AI/TLDR: `https://ai-tldr.dev/ai/archives`, not the landing page. Entries are release cards, "Name - what happened", with a source link; some are YouTube videos and funding news. `web_fetch` returns the text without dates or links: look each title up with `web_search` for the source URL and date. No date found: use the day you saw it.

A site that fails twice: say so in the report and go on. Never invent a story.

## Match

Our table is `article`, our time is `created_at`. Their time is theirs. Run it per competitor, with its stories in `t`. Match by URL, then by title:

```sql
with t(url, title, seen_at) as (values
  ('https://example.com/post', 'Their title', '2026-11-20 09:00+00'::timestamptz))
select t.url, t.title, a.url as our_url, a.created_at as ours_at,
  round(extract(epoch from t.seen_at - a.created_at) / 3600) as hours_ahead,
  r.stage, r.reason, r.detail::text as detail
from t
left join article a on rtrim(a.url, '/') = rtrim(t.url, '/') or lower(a.title) = lower(t.title)
left join scored_url r on rtrim(r.url, '/') = rtrim(t.url, '/') or lower(r.title) = lower(t.title)
```

- `our_url` set: ours. `hours_ahead` is positive when we published first, negative when they did.
- `stage` `below_threshold`: rejected, `reason` says why. Other stages (`prefilter`, `duplicate`, `thin_repo`, `unusable_summary`): rejected, read `detail`. Don't re-queue.
- `stage` `pending`: queued already, wait for curation.
- No row: we never saw it. Check its publisher:

```sql
select slug, is_active, type from publisher where links::text ilike '%example.com%'
```

## Act

1. Never seen, known or unknown publisher: `queue_candidate(url, reason)`. Reason: competitor, date, where it ran, e.g. `"AINews 2026-11-20, lead story"`. A refusal ("already known", "No readable text", "event or reference page", "star floor", "names no publisher") is the answer: note it, move on.
2. Never seen and no publisher row: first `add_publisher(url, reason)`, same reason. Then `find_feed` and `activate_publisher` only if it passes `discover-publishers`: follow its "Probing" and "The bar". A publisher that fails stays inactive.
3. At most 10 `queue_candidate` calls a run, the ones that look most like our archive. Count the rest in the report.

## Features

Open each competitor's site as a reader. Name one feature it has that we lack (filters, digests by topic, search, alerts, a tracker, an API). Max one per competitor, none if nothing stands out. Read `reports/ledger.md` first (see `docs/reports.md`, Publishing) and skip an idea already there. Each is a proposal: a ledger id, what it is, why readers would use it. Build nothing.

## Report

Per `docs/reports.md`: file `reports/<date>/watch-competitors.md`, at most 5 bullets, each ending in a proposal or a number. Publish with the commands there.

- One bullet starts `Ahead:`. Our biggest leads, up to 3, each as `URL +Nh (competitor)`. `draft-distribution` reads this bullet. No lead: `Ahead: none this week`.
- One bullet for where we were behind (count, largest gap) and what we rejected (count, most common reason, any we think were wrong).
- One bullet for what you queued and added: counts, publishers added, activated.
- One `Features:` bullet with every proposal, each with its ledger id. Then the `Ledger:` lines.

If a tool errors or a site was unreadable, name it in the last bullet. Don't edit files in the repo or commit to master.
