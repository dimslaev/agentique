---
name: scout-revenue
description: Rank the companies whose own posts agentique approved as sponsor leads, check on the web whether they sponsor other AI newsletters, and propose one revenue experiment with its cost and metric. Use when running the Tuesday revenue scout session, or when asked for sponsor leads or a revenue idea.
---

# Scout revenue

Weekly: a sponsor list and one revenue experiment. You write a report only. Nothing reaches prod.

## Tools

`agentique-admin` MCP: `sql_query` (read-only), `web_search`, `web_fetch`. Git, to publish the report.

## Sponsor list

Companies and labs whose own posts we approved. 90 days: long enough for a steady count, short enough that a publisher gone quiet drops off.

```sql
select p.slug, p.name, p.kind, p.links->>'website' as website,
  count(*) as approvals, coalesce(sum(l.n), 0) as likes, round(avg(a.score)) as avg_score
from article a
join publisher p on p.id = a.publisher_id
left join (select article_id, count(*) as n from article_like group by article_id) l
  on l.article_id = a.id
where p.kind in ('company', 'lab')
  and a.marked_for_deletion_at is null
  and coalesce(a.published_at, a.created_at) >= now() - interval '90 days'
group by p.id
order by approvals desc, likes desc
limit 15
```

Numbers for the experiment:

```sql
select count(*) as subscribers,
  count(*) filter (where created_at >= now() - interval '28 days') as new_28d
from newsletter_subscriber
```

Human traffic, last 30 days. Prefix the `with seen ..., human as (...)` block from `.claude/skills/scout-archive/SKILL.md`, so both scouts filter bots the same way:

```sql
select count(distinct visitor_id) as visitors_30d, count(*) as pageviews_30d
from human where event = 'pageview'
```

## Steps

1. Read the ledger first (`docs/reports.md`, "Reading"). List every id so you never repeat one.
2. Run the sponsor query. Take the top 5 rows. Fewer rows is fine.
3. For each of the 5, one `web_search`: `"<company>" sponsor AI newsletter` plus its name. Evidence is a URL showing it sponsoring or advertising in a named newsletter, with the date. Nothing found after that one search is a result: write "no evidence".
4. Run the two number queries. A zero is a number, report it.
5. Pick one experiment that is not in the ledger. Ideas: a sponsor slot in the newsletter, a sponsored "tool of the week" line, a paid job listing, a reader-supported tier, a data or API license. Prefer the one the numbers best support.
6. State its cost (hours or money), the metric that decides it, the threshold, and the number that makes it worth trying (a subscriber count, traffic, a lead from the list).
7. Don't contact anyone. Don't draft outreach.

## Report

Format in `docs/reports.md`. Write it to `/tmp/scout-revenue.md`, then `scripts/publish-report.sh scout-revenue /tmp/scout-revenue.md`.

- Sponsor list: top 5 with approvals, likes, evidence URL or "no evidence"
- Subscribers and traffic numbers
- The experiment: what, cost, metric and threshold, the number that backs it
- Tool errors

Ledger: one line for the experiment, `- <id> | <one line> | proposed`. No lines if no new experiment is worth running.

If `sql_query` is missing or says "Authorization failed", stop and say so.
