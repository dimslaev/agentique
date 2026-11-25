---
name: scout-competitors
description: Compare last week's top stories at AINews, Aligned News and AI/TLDR with ours - which we ran first, which we rejected and why, which never reached us - and name one feature each has that we lack. Read-only. Use when rank-proposals starts it, or when asked to watch, diff or benchmark competitors.
---

# Scout competitors

Diff the competitors' last week against ours. You read and report. You never write to prod or build anything.

All three are already sources: the nightly run reads AINews issues from the Latent Space feed, AI/TLDR by mail and Aligned News by RSS. A story of theirs that never reached us is a gap in that source, not a link to queue by hand.

## Tools

`agentique-admin` MCP: `sql_query` (reads `article`, `scored_url` and `publisher`), `web_fetch`, `web_search`.

## Read each competitor

Last 7 days. Per story keep: title, URL it links to, their date. Top stories only, about 15 per competitor.

- AINews: `https://latent.space/feeds/news.xml` holds the daily `[AINews]` issues with their full text. The stories are its own bold headlines with links; skip the Discord and Twitter recaps.
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
  r.stage, r.reason, r.source, r.detail::text as detail
from t
left join article a on rtrim(a.url, '/') = rtrim(t.url, '/') or lower(a.title) = lower(t.title)
left join scored_url r on rtrim(r.url, '/') = rtrim(t.url, '/') or lower(r.title) = lower(t.title)
order by t.url, (rtrim(a.url, '/') = rtrim(t.url, '/')) desc nulls last,
  (rtrim(r.url, '/') = rtrim(t.url, '/')) desc nulls last
```

One row per story, a URL match before a title match.

- `our_url` set: ours. `hours_ahead` is positive when we published first, negative when they did. `source` is where we first saw it; the competitor's own name there means we had it only through them.
- `stage` `below_threshold`: rejected, `reason` says why. Other stages (`prefilter`, `duplicate`, `thin_repo`, `unusable_summary`): dropped by the pipeline, read `detail`.
- `stage` `pending`: queued, not judged yet.
- No row: it never reached us. Name the likely cause: older than the run's 48-hour window, a link the issue reader dropped, a site that blocks us.

## Features

Open each competitor's site as a reader. Name one feature it has that we lack (filters, digests by topic, search, alerts, a tracker, an API). At most one per competitor, none if nothing stands out. Skip an idea already in the ledger. Each is a proposal: an id, what it is, why readers would use it.

## Report

Format in `docs/proposals.md`: at most 5 bullets, each ending in a proposal or a number.

- One bullet starts `Ahead:`. Our biggest leads among dated stories, up to 3, each as `URL +Nh (competitor)`. No lead: `Ahead: none this week`.
- One bullet for where we were behind (count, largest gap) and what we rejected (count, most common reason, any we think were wrong, with URLs).
- One bullet for what never reached us: count per competitor and the most common cause.
- One `Features:` bullet with every proposal. Then the `Ledger:` lines.

Name any tool error or unreadable site in the last bullet. Return the report as your final message. Write nothing to the repo or prod.
