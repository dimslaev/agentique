---
name: draft-newsletter
description: Draft the weekly agentique issue - choose the 10-12 most useful articles of the last 7 days, with liked articles first, then score and value to builders, mix individual and company sources, group them into sections and give each one a short summary. Use when running the Friday newsletter session, or when asked to draft or write the weekly issue.
---

# Draft the weekly issue

One issue a week: 10-12 links in 3-4 sections, one-line summary each. Same file for the email and the blog. A person reads and sends it.

## Tools

`agentique-admin` MCP: `get_last_week_articles`, `sql_query`, `web_fetch`, `web_search`, `check_repo`, `draft_newsletter`. `draft_newsletter` sends nothing.

## Steps

1. Call `get_last_week_articles()` once. `liked` can be older than the week.
2. Rank liked first, then by score. An article older than two weeks needs a clear reason.
3. Keep only articles where you can name what a builder would do after reading. Drop funding, pricing and availability news, benchmarks with no method, and results nobody can use.
4. If a pick reposts someone else's work, link the original. Find it with web search or a keyword search in `sql_query` (`article.search_tsv`, `websearch_to_tsquery`). Say in the report if it's not in the database.
5. One article per story.
6. At least 3 from individuals or communities, at most 2 per publisher. Personal domains, Substacks and github.io count as individual even when filed as `media`. Swap the lowest pick to get there, never with one that failed step 3. Say so if the week can't reach it.
7. Group into 3-4 sections named for what the articles share, like `Code review` or `Models`. 2+ articles per section. Strongest section and article first. Don't reuse last week's names by habit.
8. Write summaries with `.claude/skills/write-summary/SKILL.md`, from the stored `summary`. `web_fetch` the article if that's not enough.
9. Call `draft_newsletter(post)`. Fix what it refuses and call again.

## Format

```
---
title: The most interesting stuff this week
description: Agents reviewing code, swarms picking leaders by list order, and a 1-trillion-parameter open model.
topic: most-interesting-this-week
---
Code review

- [Article title](https://example.com/post). The summary.
- [Title that ends in a question?](https://example.com/other) The summary.

Models

- [Article title](https://example.com/post). The summary.
```

- Title is always the same.
- Description names the three biggest themes, 160 characters max.
- Section names are plain lines. The email has no headings or bold.
- Link text is the article title, without "(7 minute read)".
- No intro, closing or first person.
- Under 150 words is refused. Add a link, don't pad.
- Every URL comes from a tool.

## Finish

Save to `frontend/content/blog/<YYYY-MM-DD>-most-interesting-stuff-this-week-<YYYY-MM-DD>.md`, not the path `draft_newsletter` returns. Add `sources: false` below `topic` in the saved file only; `draft_newsletter` refuses it.

Branch `feat/weekly-issue-<YYYY-MM-DD>`, one commit `feat: weekly issue <YYYY-MM-DD>`, only that file. Push and open a PR with the same title.

Report:

- each pick: section, publisher, liked or not, what a builder would do with it
- dropped liked and top-score articles, and why
- originals swapped in, and any not in the database
- count from individuals and communities
- what `draft_newsletter` returned, and the PR link

If `get_last_week_articles` is missing or says "Authorization failed", stop and say so.
