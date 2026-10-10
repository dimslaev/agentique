# 16. A separate routine names the rail's stories

## Status

Accepted.

## Context

The feed's right rail shows stories: named threads that run over days or
weeks, like "Codemode" or "Decision models", each with a two-sentence blurb
and its articles in order.

A story is wider than coverage. Coverage (`similar`, `stories`, 0.30 cosine)
is one event told by several outlets, and the embedding maths finds it on its
own. A story is a theme a builder follows across several events: a launch, a
repo built on it, a writer who measured it. Grouping by distance alone either
misses those or chains unrelated articles together, and nothing in the maths
can name the result. That takes judgment, so an agent names and keeps stories.

The curation agent (ADR 9) already reads every article and calls `stories()`
each night, so the obvious place was a new `approve()` argument naming the
story an article joins.

## Decision

    daily 06:17:  story_candidates -> extend open stories, start new ones, close quiet ones
    the rail:     GET /api/v1/stories reads what the routine saved

- **A third routine.** A scheduled task on claude.ai/code, like curation and
  the newsletter, runs `.claude/skills/stories/SKILL.md` with the write token,
  daily after curation and the report.
- **Two tables.** `story` (slug, name, blurb, last_article_at, closed_at) and
  `story_article`. An article sits in at most one open story; `save_story`
  enforces it, being the only writer.
- **Three tools.** `story_candidates` shows the open stories and the recent
  articles in none, clustered at `STORY_DIST` (0.40) with curation's
  `story_groups`; `save_story` creates or extends one and checks the labels;
  `close_story` closes one.
- **The rail filters.** A story is public once it has 3 articles from 2
  publishers; below that it is the routine's working state.

## Why not in `approve`

- The curation rubric stays untouched. Changing it means re-running its
  regression set (CLAUDE.md), and a story field on every approval is a rubric
  change.
- The curation session is already long. Naming a story needs the open stories
  and the last two weeks in view at once, which is a different read from
  judging one candidate.
- A story is decided over days, not per article. Most articles join a story
  after it exists, and one session a day can look back over the window.

## Consequences

Stories cost one short session a day and two tables. An article approved at
05:00 joins its story at 06:17, so the rail is at most a day behind the feed.

`STORY_DIST` is a first value. It was not tuned on production data when this
shipped; the routine's reports will show whether clusters come back too broad
or too thin.

A wrong story stays on the rail until the next run fixes it or a person closes
it with `close_story`. Stories close after 21 quiet days by the skill's rule,
not by a timer.
