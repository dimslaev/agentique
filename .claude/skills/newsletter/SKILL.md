---
name: newsletter
description: Draft the weekly agentique newsletter from the week's published articles - pick the best stories, back each one with an individual writer's take, a repo or a paper, and draft it as a Resend broadcast. Use when running the Friday newsletter session, or when asked to draft, write or preview the weekly issue.
---

# Draft the weekly issue

The feed already judged every article: the curation agent read each one,
scored it and wrote its summary. You do not re-judge. You pick the stories a
builder most needs from the week, find what backs each one, and write the email.

The reader builds with AI and gets one email a week from us. It should leave
them knowing what shipped and with something to open: a post that measured it,
a repo that uses it.

## Tools

From the `agentique` MCP server, with the curation token:

- `week(days=7, min_score=70)` - the week's articles grouped into stories,
  highest `top_score` first, then widest `coverage`. Each article carries
  `publisher_kind`, `kind`, `score`, `likes` and the curation `summary`.
- `related(url, days=30, limit=12)` - what else covers one article's subject:
  published articles and rejects scored 55+, closest first, with `distance`
  (under 0.30 the same story, up to 0.45 the same subject), `summary` for a
  published row and curation's `reason` for a rejected one.
- `check_link(url)` - stars, last push, README for a repo; downloads and
  weights for a model.
- `web_search(query)`, `web_fetch(url)` - see **Looking further**.
- `sql_query(sql)` - read-only, for anything the tools above do not answer.
- `draft_issue(subject, preheader, intro, stories, quick_hits)` - renders the
  issue into the template, creates a Resend draft and mails a preview.
- `send_issue(broadcast_id)` - mails every subscriber. **Never call it** unless
  a person in this session read the preview and asked you to.

## Rounds

1. **`week()` once.** Read every story before picking any.
2. **Pick 3-5 stories:** a lead and 2-4 more. See **Picking**.
3. **`related(url)` for each picked story.** Pick its go-further links. See
   **Go further**.
4. **Look further** only where the rules below say to.
5. **Pick 4-8 quick hits.**
6. **Write**, check, and `draft_issue`.

If `week()` has fewer than 3 stories, draft with what there is. If it has
none, do not draft: report that the week was empty.

## Picking

- **The lead** is the story a builder most needs to know about this week. Start
  from `top_score`; among close scores, reach decides: coverage of 3 or more, a
  first-party release, likes. A 90+ release you can run today beats an 85
  write-up; an 85 write-up with measurements beats an 88 retold announcement.
- **The rest:** next highest score, but no two stories on the same subject, and
  a mix - not all model releases, not all dev tooling. At most one Claude Code
  story.
- **Which article stands for a story:** the first-party one (the maker's own
  post) when the group has one, otherwise the highest-scored. The other members
  are copies of it: never link them.
- **Skip** availability and pricing notices, and any story whose summary gives
  you nothing concrete to say.

## Go further

For each story, up to 2 links (3 at most), in this order of preference:

1. **An individual writer** who tested, benchmarked or built with the thing.
   `publisher_kind = individual` is reliable when set, but publishers the
   pipeline created on its own default to `media`: read the URL and the name
   too. A personal domain, a Substack, a github.io page is usually one person.
2. **A repo** that uses or extends it (`kind = repo`, a GitHub or GitLab URL).
   `check_link` it: skip archived repos, repos with no README, and repos with
   no push in months.
3. **A paper, or a first-party doc** that explains how it works.

A `rejected` row can be a go-further link when its `reason` says it was turned
down as a retelling of a story the feed already carried and it shows something
of its own - numbers, code, steps. A row rejected for scope or quality is not.

Never link a news outlet's retelling of the same announcement, the story's own
URL, or an article already used in the issue. A story with nothing worth
linking gets no go-further links. Empty beats filler.

## Looking further

- **Only for the lead**, and only when `related` gives neither an individual
  take nor a repo: search for one ("<thing> benchmark", "<thing> review",
  "github <thing>"). `web_fetch` a hit before linking it: it must be real, on
  the subject, and show something. `check_link` a repo.
- At most 5 searches and 5 fetches in the whole session.
- Do not fetch articles from `week()` to write their bodies: the summary was
  written by an agent that read the whole article. Fetch one only when its
  summary is empty or too thin for two sentences.

## Quick hits

Articles from `week()` scored 75 or more that are not already in the issue, as
a story or a go-further link. One line each: what it is and why a builder would
open it. Vary the subjects.

## Writing

- **Subject:** the lead, concrete, under 70 characters. "Ollama runs on MLX,
  twice as fast on a Mac", not "This week in AI".
- **Preheader:** the next two stories, one line.
- **Intro:** 2-3 sentences. The thread through the week if there is one,
  otherwise the lead. No greeting, no "welcome to".
- **Story title:** a plain statement of what happened, not the article's
  headline.
- **Story body:** the lead about 120 words, the others about 60. What shipped or
  was shown, the numbers with their method, what a reader would do with it.
  Plain text, a blank line between paragraphs, no markdown, no emoji.
- **Go-further note:** one line on what the link adds: "measured it on three
  Macs", "a CI setup built on it". `by` is the writer's name when you know it,
  else the publisher.
- No marketing adjectives, no "exciting", no "this article discusses". A number
  without its method gets its method or gets cut. Terse and concrete, like the
  feed's summaries.

Before drafting, check: every URL came from `week()`, `related()` or a page you
fetched, never from memory; no URL appears twice; 3-5 stories.

## Finish

Call `draft_issue`. Do not call `send_issue`. Then report:

- the stories picked, and why the lead
- each go-further link and where it came from (related published, related
  rejected, search)
- how many searches, fetches and `check_link` calls you made
- the line `draft_issue` returned

If a tool answers "This tool needs the curation token", stop and say so: the
session has the read token, not the write token.
