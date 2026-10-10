---
name: stories
description: Keep the right rail's stories - name the threads that run over days or weeks in agentique's feed, add new articles to them, and close the ones that went quiet. Use when running the daily stories session, or when asked to update, name or close stories.
---

# Keep the stories

A story is a theme a builder follows over days or weeks: "Codemode",
"Decision models". The right rail shows each one with a two-sentence blurb and
its articles in order. You decide what is a story, name it, and keep it up to
date. Nothing else writes stories.

A story is wider than coverage. Coverage is one event told by several outlets
(curation's `similar` and `stories`, at 0.30). A story is several events on
one theme: a launch, a repo built on it, a writer who measured it, a rival's
take a week later.

## Tools

From the `agentique` MCP server, with the curation token:

- `story_candidates(days=14)` - `open`: every open story with its newest 5
  articles and `quiet_days` (since its newest article was published).
  `clusters`: the last `days` of articles in no open story, grouped by
  embedding, the most publishers first. Each has `articles` (with the
  `summary` curation wrote), `publishers`, and `near`: open stories one of its
  articles sits close to. A single article close to a story comes back as a
  cluster of one with that story in `near`.
- `save_story(slug, name, blurb, urls)` - create a story, or update an open
  one: set its name and blurb, add `urls` (ones already in it are skipped).
  Refuses the whole call, saying why, on an unknown URL, an article already in
  another open story, a bad slug, a name over 4 words, or a blurb over 2
  sentences or 280 characters.
- `close_story(slug)` - close an open story. It leaves the rail and its
  articles are free to join another.
- `sql_query(sql)` - read-only, for anything the tools do not answer.

The rail shows an open story once it has 3 articles from 2 publishers.

## Rounds

1. **`story_candidates()` once.** Read every open story and every cluster
   before saving anything.
2. **Extend.** For each cluster with a story in `near`: add the articles that
   belong to that story's theme. Pass the story's current name and blurb
   unless one is now wrong (see **Keeping them stable**).
3. **Start.** For each cluster left that is a story (see **What is a story**),
   create one. Before you do, check the open stories again: an article that
   fits an open story goes there, even when `near` did not name it.
4. **Close.** Close every open story with `quiet_days` of 21 or more.
5. **Report.** See **Finish**.

## What is a story

All of these:

- 3 or more articles from 2 or more publishers, on one theme.
- A theme a builder can act on: a technique, a protocol, a kind of model, a
  way of working. Something they could try, adopt or decide against.
- More than one event. A single launch and its retellings are coverage, not a
  story, however many outlets carried it.
- Not one vendor's product line. "Claude releases" is a feed filter; "Computer
  use" is a story when several makers and writers are working on it.

A cluster is a hint, not a verdict. Split one that holds two themes, and leave
out an article that is only near by wording. A cluster of two can start a story
when a third article in the window plainly belongs to it.

## Naming

- **Name:** 1-3 words, the term people use. "Codemode", not "Code execution
  with MCP tools". "Decision models", not "Small models for agent routing".
  If the articles use one name for it, use that name.
- **Slug:** the name in lowercase with hyphens: `codemode`,
  `decision-models`. It never changes, so pick it with the name.
- **Blurb:** two plain sentences. The first says what it is, the second why it
  matters now. Under 280 characters. The newsletter's plain tone without the
  "I": no hype words, no em dashes, no "game-changer", no "landscape".
  "The agent writes a short program against your tools instead of calling them
  one at a time. Tool definitions stay out of the context; only the result
  comes back."

## Keeping them stable

- Add to an open story before starting a new one. Two open stories on one
  theme split the rail.
- Never rename a story without cause. Cause is: the field settled on another
  name for the thing, or the name was wrong. A new article is not a cause.
- Rewrite a blurb only when "why it matters now" is no longer true.
- A closed story stays closed. If its theme comes back, start a new story
  under a new slug.

## Finish

Report, short:

- created: slug, name, article count, and the line that decided it is a story
- extended: slug and how many articles added
- closed: slug and its quiet days
- clusters passed over that came close, and why
- anything a tool refused and what you did

Do not edit files or commit anything; this session reads and writes stories,
nothing else. If a tool answers "This tool needs the curation token", stop and
say so: the session has the read token, not the write token.
