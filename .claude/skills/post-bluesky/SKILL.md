---
name: post-bluesky
description: Run agentique's Bluesky account - link the Bluesky accounts of the publishers approved this morning, and post up to 5 of today's articles whose author can be tagged. Use when running the lunchtime Bluesky session, or when asked to post to Bluesky or link publishers' Bluesky accounts.
---

# Post to Bluesky

Everything here is public and posts as agentique.ch. A wrong tag notifies a stranger, so tag only accounts confirmed to be the author's.

## Tools

`agentique-admin` MCP: `sql_query`, `find_bluesky_account`, `link_bluesky_account`, `post_bluesky`.

## 1. This morning's articles

The routine runs at lunch, after the night's curation. Post what was approved today.

```sql
select a.id, a.title, a.url, a.score, a.summary, p.slug, p.name as publisher, p.kind,
  p.links->>'bluesky' as bluesky, p.links->>'website' as website,
  array(select t.slug from article_tag at join tag t on t.id = at.tag_id
    where at.article_id = a.id) as tags
from article a join publisher p on p.id = a.publisher_id
where a.created_at >= current_date and a.marked_for_deletion_at is null
order by a.score desc
```

## 2. Link

For each publisher in the list with no `bluesky` value, call `find_bluesky_account(slug)` once. Skip `community` publishers (HN, Reddit, arXiv) and aggregators.

Link a candidate with `link_bluesky_account(slug, handle)` only when one of these holds:

- the handle is the publisher's website host, or a subdomain of it
- the bio links the publisher's site or names its project
- the name and bio clearly match, and the account has posts

Never link an account with 0 posts, a mirror or bot account, or an employee for a company. If nothing passes, skip it. Linking follows no one; only the tag in the post reaches the author.

## 3. Pick up to 5

From step 1, only articles whose publisher has a linked account (step 2 or already linked) and where a builder could do something after reading. Highest score first, at most one per publisher.

Never post an article whose author can't be tagged. A day with no taggable article posts nothing.

## 4. Post each one

One `post_bluesky` call per pick:

- `text`: one plain sentence with the article's main point, written with `.claude/skills/write-summary/SKILL.md`. Then ` by @handle`. Then a new line with 1-3 hashtags from the article's `tags`, lowercase with dashes removed: `context-engineering` is `#contextengineering`. No tags, no hashtag line.
- `url`: the article URL. `title`: the article title. `description`: the stored summary's first sentence.
- No hashtags beyond the article's tags, no emoji, no "must read", no first person.

`post_bluesky` turns each `#tag` into a clickable hashtag. It refuses a URL already posted, an unknown handle and text over 300 characters. Fix and call again; skip an already-posted URL.

## Report

- accounts linked, with the reason each passed
- candidates rejected, and why
- each post's link and who it tagged, and the good articles left out because no author could be tagged

If a tool is missing or says "Authorization failed", stop and say so.
