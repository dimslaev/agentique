---
name: draft-distribution
description: Draft 2-3 Bluesky posts and one Hacker News submission from last week's most-liked articles and the latest competitor findings. Drafts only. Use when running the Tuesday distribution session, or when asked to draft social posts or an HN submission.
---

# Draft distribution

Weekly drafts for a person to post. Nothing here posts anywhere.

## Tools

`agentique-admin` MCP: `sql_query` (read-only), `web_fetch`. Git, to read and publish reports.

## Inputs

Most-liked articles, last 7 days:

```sql
select a.url, a.title, p.name as publisher, p.kind, count(*) as likes, a.score, a.summary
from article_like l
join article a on a.id = l.article_id
join publisher p on p.id = a.publisher_id
where l.created_at >= now() - interval '7 days'
  and a.marked_for_deletion_at is null
group by a.id, p.name, p.kind
order by likes desc, a.score desc
limit 8
```

Competitor findings: the `Ahead:` bullet of the newest `reports/*/watch-competitors.md` on the `reports` branch.

```bash
git fetch origin reports
F=$(git ls-tree -r --name-only FETCH_HEAD reports | grep 'watch-competitors.md$' | sort | tail -1)
git show "FETCH_HEAD:$F"
```

It names each URL and how many hours ahead we were.

## Empty inputs

- No likes: use the top 5 by `score` from the last 7 days and say so in the report.
- No `reports` branch, no watch-competitors report or no `Ahead:` bullet: use the likes alone and say so.
- Both empty: write the report with no drafts and say why.

## Steps

1. Read the inputs. Skim `frontend/content/blog/` and `.claude/skills/draft-newsletter/SKILL.md` for the voice: plain, specific, what a builder can do with it.
2. Pick 2-3 articles for Bluesky. Include one "we had it first" story if there is one. Mix publishers.
3. Write each post: under 300 characters including the link. One or two plain sentences saying what the article shows. No hashtags, hype, emoji or first-person claims. Count the characters.
4. Pick one article for HN and write the submission.
5. Check every URL comes from the inputs. `web_fetch` the HN pick to confirm it loads.

## Links

- Bluesky: link the original article.
- HN: prefer the original article over any agentique page. HN removes reposts and aggregator pages, and a page of ours that only links elsewhere reads as self-promotion. Only submit our own page (`agentique.ch/blog/...`) if it is original writing.

## HN title

- Under 80 characters. The article's own title where it fits, trimmed only by dropping a site suffix.
- No editorializing, numbers added, superlatives, caps or "how" rewrites.
- No "Show HN" unless the pick is a project of ours.

## Report

`reports/<date>/draft-distribution.md`, written and pushed as `docs/reports.md` says. Put each draft in the file under its bullet, with its character count.

- Each Bluesky post: text, link, why this article
- The HN submission: title, URL, why
- Which input was empty or missing
- Tool errors

Ledger: none. Drafts aren't proposals. Write no `Ledger:` lines.

If `sql_query` is missing or says "Authorization failed", stop and say so.
