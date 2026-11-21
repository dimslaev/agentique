---
name: update-stories
description: Keep the right rail's stories - name the threads that run over days or weeks in agentique's feed, add new articles to them, and close the ones that went quiet. Use when running the daily stories session, or when asked to update, name or close stories.
---

# Keep the stories

A story is a theme builders follow over days or weeks, like "Codemode" or "Decision models".

## Tools

`agentique-admin` MCP: `sql_query` to read, `save_story` and `close_story` to write.

Open stories:

```sql
select s.slug, s.name, s.blurb, now()::date - s.last_article_at::date as quiet_days,
  a.url, a.title, p.name as publisher, coalesce(a.published_at, a.created_at)::date as published
from story s
join story_article sa on sa.story_id = s.id
join article a on a.id = sa.article_id
join publisher p on p.id = a.publisher_id
where s.closed_at is null
order by s.last_article_at desc, published desc
```

Last 14 days, not in an open story:

```sql
select a.url, a.title, p.name as publisher, coalesce(a.published_at, a.created_at)::date as published, a.summary
from article a
join publisher p on p.id = a.publisher_id
where coalesce(a.published_at, a.created_at) >= now() - interval '14 days'
  and a.marked_for_deletion_at is null
  and not exists (select 1 from story_article sa join story s on s.id = sa.story_id
                  where sa.article_id = a.id and s.closed_at is null)
order by published
```

Keyword search, last 30 days (`or`, `"phrase"`, `-word` work):

```sql
select a.url, a.title, p.name as publisher, coalesce(a.published_at, a.created_at)::date as published, a.summary,
  (select s.slug from story_article sa join story s on s.id = sa.story_id
   where sa.article_id = a.id and s.closed_at is null) as story
from article a
join publisher p on p.id = a.publisher_id,
  websearch_to_tsquery('english', 'mlx or ollama or "llama.cpp"') q
where a.search_tsv @@ q
  and coalesce(a.published_at, a.created_at) >= now() - interval '30 days'
  and a.marked_for_deletion_at is null
order by ts_rank(a.search_tsv, q) desc
limit 30
```

## Steps

1. Read the open stories and the last 14 days.
2. For each open story, search 2-4 times with different words and add what fits.
3. Group the rest by theme. Search each theme the same way, then start the ones that are stories.
4. Close stories quiet for 21+ days.

## What is a story

- 3+ articles from 2+ publishers.
- Something a builder can try or adopt: a technique, protocol, kind of model, way of working.
- More than one event. One launch or paper and its reposts is not a story.
- Not one vendor's product line.
- Add an article only if it's on the theme, not because it shares a word.

## Names

- Name: 1-3 words, the term people use.
- Slug: the name in kebab-case. It never changes.
- Blurb: two plain sentences, under 280 characters. What it is, then why it matters now.

## Keep stable

- Add to an open story before starting a new one.
- Rename or rewrite a blurb only when it's wrong.
- A closed story stays closed. Start a new slug if the theme returns.

## Report

- Created, extended (with search words used) and closed stories.
- Close calls you passed on, and why.
- Two open stories on one theme.
- Tool errors.

Don't edit files or commit. If `save_story` is missing or says "Authorization failed", stop and say so.
