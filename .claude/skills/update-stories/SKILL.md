---
name: update-stories
description: Keep the right rail's stories - name the threads that run over days or weeks in agentique's feed, add new articles to them, and close the ones that went quiet. Use when running the daily stories session, or when asked to update, name or close stories.
---

# Keep the stories

A story is a theme a builder follows over days or weeks: "Codemode",
"Decision models". The right rail shows each one with a two-sentence blurb and
its articles in order. You decide what is a story, name it, and keep it up to
date. Nothing else writes stories.

A story is wider than a duplicate group. A duplicate group is one event reported by several publishers
(curation's `find_similar` and `find_duplicates`, at 0.30). A story is several events on
one theme: a launch, a repo built on it, a writer who measured it, a rival's
take a week later.

## Tools

From the `agentique-admin` MCP server: `list_story_candidates`, `save_story`,
`close_story`, and `sql_query` for anything they do not answer. Each tool's
description says what it returns.

## Rounds

1. **`list_story_candidates()` once.** Read every open story and every group
   before saving anything.
2. **Extend.** For each group with a story in `near`: add the articles that
   belong to that story's theme. Pass the story's current name and blurb
   unless one is now wrong (see **Keeping them stable**).
3. **Start.** For each group left that is a story (see **What is a story**),
   create one. Before you do, check the open stories again: an article that
   fits an open story goes there, even when `near` did not name it.
4. **Close.** Close every open story with `quiet_days` of 21 or more.
5. **Report.** See **Finish**.

## What is a story

All of these:

- 3 or more articles from 2 or more publishers, on one theme.
- A theme a builder can act on: a technique, a protocol, a kind of model, a
  way of working. Something they could try, adopt or decide against.
- More than one event. A single launch and its reposts are duplicates, not a
  story, however many publishers carried it.
- Not one vendor's product line. "Claude releases" is a feed filter; "Computer
  use" is a story when several creators and writers are working on it.

A group is a hint, not a verdict. Split one that holds two themes, and leave
out an article that is only near by wording. A group of two can start a story
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
- groups passed over that came close, and why
- anything a tool refused and what you did

Do not edit files or commit. If `list_story_candidates` is missing or answers
"Authorization failed", the session has the read token: stop and say so.
