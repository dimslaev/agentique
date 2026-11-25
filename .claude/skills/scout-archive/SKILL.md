---
name: scout-archive
description: Propose up to 3 product ideas the archive could support, each backed by a number from the db, such as per-tag digests, feeds built from likes, best-of pages, or a paid API or dataset. Use when running the Tuesday archive scout session, or when asked for product ideas from the archive.
---

# Scout the archive

Find products the archive's data already supports. You propose, a person decides. You never build or publish.

## Tools

- `agentique-admin` MCP: `sql_query` (read-only, 10 s, 1000 rows; no `user` table), `web_search` (one per idea), `list_tags`.
- git, to read the ledger and publish the report. Layout, format and commands: `docs/reports.md`.

## Steps

1. Read `reports/ledger.md` as `docs/reports.md` describes. Skip every idea in it. Cite its id only with new evidence.
2. Check what the site has: `frontend/src/routes/` and `backend/app/entry/api/`. Today: the feed with tag, publisher and search filters, stories rail, likes, weekly newsletter, `connect-mcp` page, analytics. No RSS feed, no public per-tag pages, no paid API. Never propose what exists.
3. Run the queries below. Add your own if an idea needs one, read-only.
4. Pick up to 3 ideas, each with a number from step 3. No number, no idea.
5. Per idea, one `web_search` for who already sells it and at what price. Note the answer in one clause.
6. Write and publish the report.

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

Human pageviews per path, last 30 days. This copies the bot rules in `build_report` (`backend/app/features/analytics/service.py`): null or bot-like agent, and one-hit desktop Chrome scrapers (commit `bf06536`). The admin rule needs the `user` table, which you can't read, so admin views stay in. Paths have no query string. Change `human` if the service's rules change.

```sql
with seen as (select visitor_id, count(*) as hits from analytics_event where visitor_id is not null group by visitor_id),
human as (
  select e.* from analytics_event e left join seen s on s.visitor_id = e.visitor_id
  where e.created_at > now() - interval '30 days' and e.user_agent is not null
    and e.user_agent !~* 'bot|crawl|spider|slurp|scan|headless|python|curl|wget|preview|lighthouse'
    and not (e.user_agent ~ '(X11; Linux x86_64|Windows NT 10\.0).*Chrome/\d+\.0\.0\.0 Safari/537\.36$' and coalesce(s.hits, 0) <= 1)
)
select path, count(*) as views, count(distinct visitor_id) as visitors
from human where event = 'pageview' group by path order by views desc limit 20
```

Returning visitors (prefix the same `with seen ..., human as (...)` block):

```sql
select count(*) as visitors, count(*) filter (where active_days >= 2) as returning
from (select visitor_id, count(distinct date(created_at at time zone 'UTC')) as active_days
  from human where visitor_id is not null group by visitor_id) d
```

Filter use, which tags readers pick (same prefix):

```sql
select props->>'row' as row, props->>'value' as value, count(*) as clicks
from human where event = 'filter_click' group by 1, 2 order by clicks desc limit 15
```

Newsletter signups and topic picks (`categories` is a JSON list):

```sql
select count(*) as subscribers, count(*) filter (where created_at > now() - interval '30 days') as new_30d,
  count(*) filter (where categories <> '["all"]'::jsonb or custom_category <> '') as picked_topics
from newsletter_subscriber
```

Embedding coverage, for a dataset or API: `select count(*) filter (where embedding is not null) as embedded, count(*) as total from article`.

## Ideas to start from

- Per-tag digests: a tag with many articles, high scores and filter clicks.
- Feeds built from likes: likers and likes in the last 30 days.
- Best-of X evergreen pages: high-score articles per tag or publisher, paths with steady views.
- Paid API or dataset: article count, embedding coverage, score spread.
- Others the data shows: stories, publishers, returning visitors.

## Report

Format in `docs/reports.md`. Write it to `/tmp/scout-archive.md`, then `scripts/publish-report.sh scout-archive /tmp/scout-archive.md`. Each bullet: the idea, the number with its window, the search finding, one next step. One ledger line per idea, ids not in the ledger. With nothing worth proposing, write the report with no `Ledger:` lines. Don't edit files in the repo or call any write tool. If `sql_query` is missing or says "Authorization failed", stop and say so.
