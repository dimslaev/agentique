---
name: post-bluesky
description: Run agentique's Bluesky account - link and follow the Bluesky accounts of the publishers approved this morning, post today's top 5 articles with their authors tagged, and post the weekly issue once it is live. Use when running the lunchtime Bluesky session, or when asked to post to Bluesky or follow publishers there.
---

# Post to Bluesky

Everything here is public and posts as agentique.ch. A wrong tag notifies a stranger, so tag only accounts confirmed to be the author's.

## Tools

`agentique-admin` MCP: `sql_query`, `web_fetch`, `find_bluesky_account`, `link_bluesky_account`, `post_bluesky`.

## 1. This morning's articles

The routine runs at lunch, after the night's curation. Post what was approved today.

```sql
select a.id, a.title, a.url, a.score, a.summary, p.slug, p.name as publisher, p.kind,
  p.links->>'bluesky' as bluesky, p.links->>'website' as website
from article a join publisher p on p.id = a.publisher_id
where a.created_at >= current_date and a.marked_for_deletion_at is null
order by a.score desc
```

## 2. Link and follow

For each publisher in the list with no `bluesky` value, call `find_bluesky_account(slug)` once. Skip `community` publishers (HN, Reddit, arXiv) and aggregators.

Link a candidate with `link_bluesky_account(slug, handle)` only when one of these holds:

- the handle is the publisher's website host, or a subdomain of it
- the bio links the publisher's site or names its project
- the name and bio clearly match, and the account has posts

Never link an account with 0 posts, a mirror or bot account, or an employee for a company. If nothing passes, skip it. `link_bluesky_account` follows the account too, and followed accounts feed the Bluesky source, so a wrong link costs twice.

## 3. Top 5

Pick 5 from step 1: highest score first, at most one per publisher, and only articles where a builder could do something after reading. Fewer than 5 is fine on a thin day. Post nothing on a day with none.

## 4. Post each one

One `post_bluesky` call per pick:

- `text`: one plain sentence with the article's main point, written with `.claude/skills/write-summary/SKILL.md`. Then ` by @handle` if the publisher has a linked account.
- `url`: the article URL. `title`: the article title. `description`: the stored summary's first sentence.
- No hashtags, no emoji, no "must read", no first person.

`post_bluesky` refuses a URL already posted, an unknown handle and text over 300 characters. Fix and call again; skip an already-posted URL.

## 5. The weekly issue

Find the newest `frontend/content/blog/*-most-interesting-stuff-this-week-*.md`. Its URL is `https://agentique.ch/blog/<file name without the leading date and .md>/`, e.g. `2026-11-21-most-interesting-stuff-this-week-2026-11-21.md` is `https://agentique.ch/blog/most-interesting-stuff-this-week-2026-11-21/`.

If `web_fetch` gets the page (it goes live when the issue's PR merges), post it:

- `text`: `Most interesting this week for AI builders:` then 3-4 lines `• <what it does in 8 words or less>`, from the issue's own links. Add ` @handle` to a line when that article's publisher has a linked account. 300 characters max: drop lines, not tags' accuracy.
- `url`: the issue URL. `title` and `description`: the file's frontmatter.

"Already posted" means a previous run did it. Not live yet means try again tomorrow.

## Report

- accounts linked and followed, with the reason each passed
- candidates rejected, and why
- each post's link and who it tagged
- the weekly issue: posted, already posted, or not live yet

If a tool is missing or says "Authorization failed", stop and say so.
