# 22. The stories routine groups by reading, not by embedding

## Status

Accepted. Replaces the `story_candidates` clustering in ADR 16.

## Context

ADR 16 gave the stories routine one read tool, `list_story_candidates`, that
clustered the last 14 days of free articles at `STORY_DIST` (0.40 cosine) and
named the open stories each cluster came near. The routine treated each
cluster as its starting point.

By 2026-11-21 the rail showed both failures ADR 16 warned about. Stories
missed articles on their theme: "Junie Local became 70% faster on Mac M5" sat
outside `local-inference`. They held articles that only looked alike: "Agent
token costs", and "Evolutionary code search", which was not a story at all.
`local-inference` and `on-device-models` were open side by side on one theme.

## Decision

    sql_query: open stories, the 14-day window, keyword search over 30 days
    -> Opus groups by reading -> save_story | close_story

- **No clustering tool.** `list_story_candidates`, its types and `STORY_DIST`
  are gone. The skill reads through `sql_query` with fixed queries written
  in it.
- **Keyword search, not meaning.** The routine searches `article.search_tsv`
  with `websearch_to_tsquery`, 2-4 searches per theme with different terms,
  over 30 days.
- **Writes unchanged.** `save_story` and `close_story` keep their checks.

## Consequences

The window is about 540 articles, about 30k tokens, under `sql_query`'s 1000
row cap. A busier window needs a narrower query.

The skill now holds SQL no test covers. A schema change to `story`,
`story_article` or `article` has to update `.claude/skills/update-stories/`.

Stories already wrong stay until a person closes them or they go 21 days
quiet. There is still no way to remove an article from a story or merge two.
