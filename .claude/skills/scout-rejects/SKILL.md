---
name: scout-rejects
description: Read the last 30 days of rejected articles, find rejects the rubric should have kept and stages that misbehave, and propose rubric diffs with the regression cases each needs. Read-only. Use when rank-proposals starts it, or when asked to review rejects, find rubric blind spots or check the reject stages.
---

# Scout the rejects

Find what curation keeps rejecting that readers or competitors say it shouldn't. You propose, you never change the rubric.

## Tools

- `agentique-admin` MCP: `sql_query` (logs in as `agentique_ro`: every table but `user`, 10 s, 1000 rows). Nothing else.
- Never edit `.claude/skills/curate-articles/` or its `regression.md`.

## Read first

1. The ledger, from your prompt, or read it as `docs/proposals.md` says when run alone. Don't propose an id or idea already there.
2. The `scout-competitors` findings, if your prompt has them: stories we rejected or never saw. None: skip it and say so.
3. `.claude/skills/curate-articles/SKILL.md` and `regression.md`.

## What rejects carry

`scored_url` rows. `pending` is the queue, not a reject: exclude it. Stages: `below_threshold` is the agent's verdict (`score`, `reason`); `thin_repo`, `prefilter`, `duplicate`, `unusable_summary` come from the pipeline (`detail` holds the evidence). Rows have no tags and no kind. Stand-ins:
- the publisher: its tags are those of its approved articles (query 4), counted once per publisher
- the `reason` text and the title: query 5 compares a phrase in rejects against approvals
- Don't claim a tag-level reject rate. Say "via publishers carrying the tag".

## Queries

Run each once. Add a `limit` if one hits 1000 rows.

1. Stage drift, 30 days against the 30 before:

```sql
select coalesce(stage, 'none') as stage,
  count(*) filter (where created_at >= now() - interval '30 days') as last_30,
  count(*) filter (where created_at < now() - interval '30 days') as prev_30,
  round(avg(score) filter (where created_at >= now() - interval '30 days')) as avg_score
from scored_url
where stage is distinct from 'pending' and created_at >= now() - interval '60 days'
group by 1
order by last_30 desc
```

2. `below_threshold` reasons that repeat:

```sql
select lower(left(reason, 70)) as reason, count(*) as n,
  count(*) filter (where created_at < now() - interval '30 days') as prev_30,
  round(avg(score)) as avg_score,
  (array_agg(title order by score desc))[1:3] as top_titles
from scored_url
where stage = 'below_threshold' and created_at >= now() - interval '30 days'
group by 1
having count(*) >= 3
order by n desc
limit 30
```

3. Publishers: rejects, approvals and likes (likes on articles approved in the last 90 days):

```sql
select p.slug, p.kind, p.trust, r.rejected, r.avg_score,
  coalesce(a.approved, 0) as approved, coalesce(a.likes, 0) as likes
from (select publisher_id, count(*) as rejected, round(avg(score)) as avg_score
      from scored_url
      where stage is distinct from 'pending' and created_at >= now() - interval '30 days'
      group by 1) r
join publisher p on p.id = r.publisher_id
left join (select a.publisher_id, count(*) as approved, sum(l.n) as likes
           from article a
           left join (select article_id, count(*) as n from article_like group by 1) l on l.article_id = a.id
           where a.created_at >= now() - interval '90 days' and a.marked_for_deletion_at is null
           group by 1) a on a.publisher_id = r.publisher_id
where r.rejected >= 5
order by r.rejected desc
limit 40
```

4. Tags by publisher stand-in:

```sql
with rj as (
  select publisher_id, count(*) as n
  from scored_url
  where stage is distinct from 'pending' and created_at >= now() - interval '30 days'
  group by 1
), tp as (
  select distinct at.tag_id, a.publisher_id
  from article_tag at
  join article a on a.id = at.article_id
  where a.created_at >= now() - interval '90 days' and a.marked_for_deletion_at is null
)
select t.slug, count(*) as publishers, sum(coalesce(rj.n, 0)) as rejects
from tp
join tag t on t.id = tp.tag_id
left join rj on rj.publisher_id = tp.publisher_id
group by 1
order by rejects desc
limit 30
```

5. A kind of post, as a phrase (`or`, `"phrase"`, `-word` work). Replace the query in both places:

```sql
select 'rejected' as side, count(*) as n, (array_agg(title order by created_at desc))[1:5] as newest
from scored_url, websearch_to_tsquery('english', 'tutorial or "how to"') q
where stage = 'below_threshold' and created_at >= now() - interval '30 days'
  and to_tsvector('english', coalesce(title, '') || ' ' || coalesce(reason, '')) @@ q
union all
select 'approved', count(*), (array_agg(title order by created_at desc))[1:5]
from article, websearch_to_tsquery('english', 'tutorial or "how to"') q
where created_at >= now() - interval '30 days' and marked_for_deletion_at is null
  and search_tsv @@ q
```

To list a publisher's or reason's rejects, select `url, title, score, reason` from `scored_url` for it, newest first, `limit 20`.

## Patterns

- **Rubric blind spot.** A publisher or kind of post with 5+ rejects, scored 55-64 on average, and approvals that earn likes or that a competitor ran. Read 5 of its rejects and 3 liked approvals. Propose a diff only if you can say in one line what separates them.
- **Reason repeats** (query 2). 10+ rows on one reason with a score near 65 is a rule doing the work. Check it still fits `regression.md` before proposing to loosen it.
- **Stage bug.** A stage with 20+ rows and 2x its previous 30 days, or an `avg_score` far from its history. It is not a rubric issue. Read 5 rows, name the likely cause (a feed, a filter, a threshold) and propose a code or config fix.
- Reasons the rubric rightly applies (funding, console how-tos) are not findings.

## Proposed diffs

Each diff is for `.claude/skills/curate-articles/SKILL.md`:
- the section, a short quoted before and after
- the evidence: counts, 2-3 rejected URLs, the likes or competitor coverage
- the regression cases it needs, in `regression.md`'s table columns: `| label | kind | publisher | was | new | article |`. `was` is the stored score, `new` is `-` until someone runs the set. At least 3 the change should flip (`love` or `ok`) and 2 it must not (`noise`). Take them from the rejects and approvals you read.
- the risk: which current `noise` rows it could pull in

Max 3 diffs. Fewer is fine. A diff with fewer than 3 flip cases is a hunch: leave it out.

## Report

Format in `docs/proposals.md`: at most 5 bullets, then `Ledger:` lines, one per proposed diff or stage fix. Put the full diffs under `## Details` after the ledger. Bullets give the number and the proposal; the diff text lives only there.

- Rejects in 30 days by stage, and the biggest change against the 30 days before
- Each pattern found, with its count
- Each proposal and its ledger id
- Queries that errored or hit 1000 rows

A week with nothing to propose still returns a report, with no `Ledger:` lines. Return it as your final message. If `sql_query` says "Authorization failed", stop and say so.
