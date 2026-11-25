---
name: scout-growth
description: Propose up to 3 ideas for more readers or revenue that the archive's numbers back, such as per-tag digests, best-of pages, a sponsor slot or a paid API, and rank the companies we approve as sponsor leads. Read-only. Use when rank-proposals starts it, or when asked for product ideas, sponsor leads or a revenue experiment.
---

# Scout growth

Find what the archive's data already supports: a product readers would use, or a way it could earn. You propose, a person decides. You never build, publish or contact anyone.

## Tools

`agentique-admin` MCP: `sql_query` (read-only, 10 s, 1000 rows; no `user` table), `web_search`, `web_fetch`, `list_tags`.

## Steps

1. The ledger, from your prompt, or read it as `docs/proposals.md` says when run alone. Skip every idea in it. Cite its id only with new evidence.
2. Check what the site has: `frontend/src/routes/` and `backend/app/entry/api/`. Today: the feed with tag, publisher and search filters, stories rail, likes, weekly newsletter, `connect-mcp` page, analytics. No RSS feed, no public per-tag pages, no paid API. Never propose what exists.
3. Run the queries below. Add your own if an idea needs one, read-only. A zero is a number: report it.
4. Sponsor leads: the top 5 rows of the sponsor query. For each, one `web_search`: `"<company>" sponsor AI newsletter`. Evidence is a URL showing it sponsoring or advertising in a named newsletter, with the date. Nothing found is a result: "no evidence".
5. Pick up to 3 ideas, each with a number from step 3. No number, no idea. At most one is a revenue experiment; give it a cost (hours or money), the metric that decides it and its threshold.
6. Per idea, one `web_search` for who already sells it and at what price. One clause.

## Queries

Articles per tag (depth for digests and best-of pages):

```sql
select t.slug, count(*) as articles,
  count(*) filter (where coalesce(a.published_at, a.created_at) > now() - interval '30 days') as last_30d,
  round(avg(a.score)) as avg_score, count(*) filter (where a.score >= 85) as score_85_plus
from tag t join article_tag at on at.tag_id = t.id join article a on a.id = at.article_id
where a.marked_for_deletion_at is null
group by t.slug order by articles desc limit 30
```

Likes, total and per tag (feeds built from likes):

```sql
select count(*) as likes, count(distinct user_id) as likers, count(distinct article_id) as liked_articles,
  count(*) filter (where created_at > now() - interval '30 days') as likes_30d
from article_like
```

```sql
select t.slug, count(*) as likes, count(distinct l.user_id) as likers
from article_like l join article_tag at on at.article_id = l.article_id join tag t on t.id = at.tag_id
group by t.slug order by likes desc limit 15
```

Newsletter signups and topic picks (`categories` is a JSON list):

```sql
select count(*) as subscribers, count(*) filter (where created_at > now() - interval '30 days') as new_30d,
  count(*) filter (where categories <> '["all"]'::jsonb or custom_category <> '') as picked_topics
from newsletter_subscriber
```

Sponsor leads: companies and labs whose own posts we approved in 90 days, long enough for a steady count, short enough that one gone quiet drops off:

```sql
select p.slug, p.name, p.kind, p.links->>'website' as website,
  count(*) as approvals, coalesce(sum(l.n), 0) as likes, round(avg(a.score)) as avg_score
from article a
join publisher p on p.id = a.publisher_id
left join (select article_id, count(*) as n from article_like group by article_id) l on l.article_id = a.id
where p.kind in ('company', 'lab')
  and a.marked_for_deletion_at is null
  and coalesce(a.published_at, a.created_at) >= now() - interval '90 days'
group by p.id
order by approvals desc, likes desc
limit 15
```

Embedding coverage, for a dataset or API: `select count(*) filter (where embedding is not null) as embedded, count(*) as total from article`.

Human traffic. The `human` block copies the bot rules in `build_report` (`backend/app/features/analytics/service.py`): null or bot-like agent, and one-hit desktop Chrome scrapers. The admin rule needs the `user` table, which you can't read, so admin views stay in. Paths have no query string. Change `human` if the service's rules change. Prefix each query below with it:

```sql
with seen as (select visitor_id, count(*) as hits from analytics_event where visitor_id is not null group by visitor_id),
human as (
  select e.* from analytics_event e left join seen s on s.visitor_id = e.visitor_id
  where e.created_at > now() - interval '30 days' and e.user_agent is not null
    and e.user_agent !~* 'bot|crawl|spider|slurp|scan|headless|python|curl|wget|preview|lighthouse'
    and not (e.user_agent ~ '(X11; Linux x86_64|Windows NT 10\.0).*Chrome/\d+\.0\.0\.0 Safari/537\.36$' and coalesce(s.hits, 0) <= 1)
)
```

Pageviews per path, 30 days:

```sql
select path, count(*) as views, count(distinct visitor_id) as visitors
from human where event = 'pageview' group by path order by views desc limit 20
```

Visitors and returning visitors:

```sql
select count(*) as visitors, count(*) filter (where active_days >= 2) as returning
from (select visitor_id, count(distinct date(created_at at time zone 'UTC')) as active_days
  from human where visitor_id is not null group by visitor_id) d
```

Filter use, which tags readers pick:

```sql
select props->>'row' as row, props->>'value' as value, count(*) as clicks
from human where event = 'filter_click' group by 1, 2 order by clicks desc limit 15
```

## Ideas to start from

- Per-tag digests: a tag with many articles, high scores and filter clicks.
- Feeds built from likes: likers and likes in the last 30 days.
- Best-of pages: high-score articles per tag or publisher, paths with steady views.
- A sponsor slot or sponsored "tool of the week" line: subscribers, traffic, a lead from the list.
- A paid API, dataset or data license: article count, embedding coverage, score spread.
- A paid job listing or a reader-supported tier.

## Report

Format in `docs/proposals.md`. At most 5 bullets:

- Each idea: what, the number with its window, who sells it already, one next step. A revenue idea also gives its cost, metric and threshold.
- Sponsor leads: the top 5 with approvals, likes, evidence URL or "no evidence".
- Subscribers and traffic numbers.
- Tool errors.

Then one `Ledger:` line per idea. With nothing worth proposing, return the report with no `Ledger:` lines. Return it as your final message. Don't edit files in the repo or call any write tool. If `sql_query` is missing or says "Authorization failed", stop and say so.
