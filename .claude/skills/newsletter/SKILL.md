---
name: newsletter
description: Draft the weekly agentique issue - choose the 10-12 most useful articles of the last 7 days, with liked articles first, then score and value to builders, mix individual and company sources, group them into sections and give each one a short summary. Use when running the Friday newsletter session, or when asked to draft or write the weekly issue.
---

# Draft the weekly issue

Each week you draft one issue: 10-12 links in 3-4 sections, each with a one-line
summary. It is the same file for the email and the blog post. A person reads
the draft and sends it. It takes under a minute to read.

## Tools

From the `agentique` MCP server, with the curation token:

- `week(days=7, limit=40)` - the week's topics. Each article has `publisher`,
  `publisher_kind`, `kind`, `score`, `likes` and `summary`. `covered_by` lists
  the retellings curation rejected.
- `sql_query(sql)` - read-only. The `user` table is blocked.
- `related(url)` - what else covers a story, to find the original.
- `web_fetch(url)`, `web_search(query)`, `check_link(url)` - find and check an
  original source.
- `draft_issue(post)` - checks the post and creates a Resend draft. Nothing is
  sent.

If a tool answers "This tool needs the curation token", stop and say so.

## Rounds

1. **Collect.** Call `week()`, then find the articles liked in the last 7 days.
   A liked article can be older than the week:

   ```sql
   select a.title, a.url, a.score, a.published_at, a.summary, p.name, p.kind,
          count(*) as likes
   from article_like l
   join article a on a.id = l.article_id
   join publisher p on p.id = a.publisher_id
   where l.created_at >= now() - interval '7 days'
     and a.marked_for_deletion_at is null
   group by a.id, p.id
   order by likes desc, a.score desc
   ```

2. **Rank.** Liked articles come first, then the rest by `score`. Prefer articles
   published in the last two weeks. An older liked article needs a clear reason
   to stay.
3. **Check builder value.** For each one, name what a builder would do or decide
   after reading it. If you can't, drop it, whatever its score or likes. Drop
   funding, availability and pricing notices, benchmarks with no method, and
   impressive results nobody can use.
4. **Use the original.** If a pick retells someone else's work, read `related`
   or search for the maker's post, repo or paper, and link that instead. Say in
   the report when the original isn't in the database yet.
5. **Merge duplicates.** Keep one article per story.
6. **Mix sources.** Include at least 3 from individuals or communities, and no
   more than 2 from one publisher. Unknown writers are often filed as `media`,
   so also count personal domains, Substacks and github.io pages as individual.
   Swap the lowest-ranked pick to reach the mix, but never add an article that
   failed step 3. If the week can't reach it, say so.
7. **Group.** Put the picks into 3-4 sections named after what the articles have
   in common, like `Code review`, `Running agents` or `Models`. Find the
   week's themes from the picks, and don't reuse last week's names by habit.
   Each section needs at least 2 articles. Put the strongest section first and
   the strongest article first in each section.
8. **Summarize.** Read `.claude/skills/summary/SKILL.md` and write one summary
   per article from its stored `summary`. If the stored summary doesn't support
   a clear point, `web_fetch` the article.
9. **Draft.** Build the post (see **Format**) and call `draft_issue(post)`. On a
   refusal, fix what it names and call it again.
10. **Save, open a PR and report.** See **Finish**.

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

- **`title`:** always `The most interesting stuff this week`.
- **`description`:** names the week's three biggest themes, 160 characters at
  most.
- **Section names:** a plain line of text. The email renders no headings or bold.
- **Link text:** the article's title, without "(7 minute read)".
- **No intro, no closing, no first person.**
- **Length:** `draft_issue` refuses under 150 words. If it does, add a link
  rather than padding the summaries.
- Every URL comes from a tool, never from memory.

## Finish

`draft_issue` returns a path, but don't use it: this title is the same every
week. Save the post at:

```
frontend/content/blog/<YYYY-MM-DD>-most-interesting-stuff-this-week-<YYYY-MM-DD>.md
```

Add `sources: false` to the frontmatter of the saved file, below `topic`. The
blog would otherwise repeat every link in a sources list. Pass `draft_issue` the
post without it, because `draft_issue` refuses any other key.

Commit the post on a new branch, `feat/weekly-issue-<YYYY-MM-DD>`, one commit,
subject `feat: weekly issue <YYYY-MM-DD>`. Commit nothing else. Push it and open
one PR with the same title. A person sends the draft in Resend and merges the PR.

Then report:

- each pick, with its section, publisher, whether it was liked, and what a
  builder would do with it
- what you dropped from the liked articles and the top scores, and why
- originals you swapped in, and any that aren't in the database
- how many picks came from individuals and communities
- the line `draft_issue` returned, and the PR link
