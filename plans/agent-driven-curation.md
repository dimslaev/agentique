# Agent-driven curation

Replace the LLM pipeline with a dumb fetcher plus a curation agent that works
through tools.

## Why

- Better scoring, categorization and tagging than the current small-model chain.
- Much less code to maintain.
- The current pipeline is a fixed sequence: every article gets every step
  whether it needs it or not. An agent picks the steps per article — a thin HN
  link needs a fetch, a full Substack post doesn't; an aggregator item needs
  source resolution, a first-party post doesn't.

## Shape

```
pipeline (RSS + HN + AI News) -> feed_item        # no LLM, no embeddings
curation agent -> tool API -> article + tags      # all judgment lives here
```

## Phase status

| phase | what | state |
|---|---|---|
| 1 | `feed_item` table, pipeline writes to it alongside current behaviour | done |
| 2 | tool API under `/api/v1/agent/*` | done |
| 3 | agent prompt, dry-run against a restored dump | prompt written, dry run not done |
| 4 | flip: pipeline stops scoring and inserting, agent inserts for real | not started |
| 5 | delete baml, the LLM steps, the dead sources, the deps | not started |

Phase 3 is the go/no-go: run the agent in dry-run and compare its accept list
to what the LLM pipeline picked the same day. Phase 5 is one-way — once baml is
gone, reverting is a rewrite, not a `git revert`. Don't start it until a week of
phase 4 looks better than what it replaced.

## Done in phases 1-2

**`feed_item`** — the agent's inbox. `url` unique, `status` (`new` / `accepted`
/ `rejected`) plus `decision` and `decided_at`, `feed_publisher_id` for the
*carrier*, `links` for pre-parsed outbound candidates. `status` is what makes a
non-deterministic agent safe: a crashed run resumes on `new` only. Pruned at 30
days by `pipeline.steps.inbox.prune_feed_items`.

**Pipeline** — `fetch_source` now returns what the source emitted, and
`fill_content` (the old `_with_content`) is a separate call the LLM funnel makes
and the inbox does not. So the inbox keeps thin items; the funnel still drops
them. AI News stores its whole ranked candidate link list, not just the pick.
Both funnels run side by side for now.

**Tool API** — `/api/v1/agent/*`, one bearer token (`AGENT_API_TOKEN`), 503 when
unset. Reads: `feed-items`, `publishers`, `tags`, and `sql` (arbitrary SELECT on
a read-only connection with a statement timeout and a row cap). Fetch:
`fetch-url`, capped at 2 concurrent because it shares a process with the site.
Writes are typed only — `articles`, `publishers`, `tags`,
`feed-items/{id}/decision`. Semantic dedup reuses the existing public
`/articles/search`; there is no new tool for it.

**Fixed while here** — `/articles/` `min_score` was `Query(ge=1, le=100)`
declared as `le=10`, so every realistic value 422'd and the filter had never
worked.

## Deployment

`AGENT_API_TOKEN` must be set in `/opt/agentique/.env` before the agent can do
anything; without it the router serves 503.

`AGENT_READONLY_DATABASE_URI` should point at a role with SELECT and nothing
else. Without it, `sql_read` falls back to the app's own role — the read-only
transaction and the timeout still apply, which is fine locally and is not fine
in production:

```sql
CREATE ROLE agent_ro LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE app TO agent_ro;
GRANT USAGE ON SCHEMA public TO agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agent_ro;
```

## Still to do before anything is scheduled

`health.py` and the dead-man's-switch were dropped for v1 because a human is
watching each run. **This has to come back before the agent is scheduled** — a
run that dies on its first tool call produces no summary, so "the agent never
ran" is invisible without an external check.

## Explicitly out of scope

- Firecrawl. `fetch_url` with the residential-proxy fallback already covers it.
- GH Actions, cron, an OAuth token. Revisit once local runs are good.
- Semantic dedup on ingest. It is a judgment call, and the agent makes it for
  the handful of items it wants rather than for all ~100 that arrive.
- Moving HN off the firebase API. `hnrss.org` is third-party with one
  maintainer; the official feed is frontpage-only with no filter, which would
  put ~30 unfiltered items a day into the inbox.

## Pipeline changes still pending (phase 4/5)

- `WINDOW_HOURS` 168 -> 24.
- Drop the `extract_content` call at the end of `fetch_hn`.
- `run.py` collapses to: for each source, fetch, dedup by URL, insert
  `feed_item`.
- Delete `steps/score.py`, `steps/enrich.py`, `steps/filter.py`,
  `steps/persist.py`, `keep_drop.py`, `heuristics.py`, `tags.py`,
  `embedding.py`, `llm_text.py`, `health.py`, `sources/lab_watch.py`,
  `sources/email.py`, `baml_src/`, `backend/baml_client/`.
- Drop deps: baml-py, tavily, and model2vec *from the pipeline* — the backend
  still needs model2vec for `/articles/search` and for embedding what the agent
  writes.
