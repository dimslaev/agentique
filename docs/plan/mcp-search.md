# MCP search

## Shape

- Problem: signed-in developers' agents can't dig through agentique's archive. They can't browse tags, filter, or search by meaning or keyword.
- Today: search embeds title + first 200 chars with model2vec potion-8M. No keyword search. The read token reaches only `sql_query`, `web_fetch`, `web_search`.
- Direction: hybrid search (Postgres full-text + existing vector) and read-only SQL over public views, both for signed-in users over MCP.
- Content rule: search the full body, never return it. Only links and short excerpts leave the server.

## Spec

### Tokens
- Signed-in user creates an MCP token from a button in account settings, shown once.
- One active token per user, stored as a hash, no expiry, revocable.

### Endpoint
- One `/mcp`, gated by scope. `SharedSecret` gains a `user` scope that resolves per-user tokens.
- `user` scope sees only `search`, `tags`, `sql_query` (public). Internal tools are hidden from its tool list, not just refused.

### Public SQL
- Postgres role `mcp_public`, SELECT only on schema `public_api`.
- Role settings: `statement_timeout=3s`, connection limit 5. Password in `.env`.
- Role and views are created in a migration.

### Views (`public_api`)
- `article`: id, title, url, publisher_id, published_at, score, kind, summary, like_count. No content, no score_reason.
- `publisher`: id, name, kind, url.
- `tag`: id, slug.
- `article_tag`: article_id, tag_id.
- Excluded: users, per-user likes, ledger, runs, stories, analytics, newsletter.

### Search
- Generated `tsvector` column over title, summary, content, with GIN index. Title also indexed with the `simple` config so tokens like `gpt-4o` match.
- Tag names and slugs are searched too, at query time, weighted like the title. The query's words must all be in the text or all in one tag.
- Ranking: plain reciprocal rank fusion of the full-text rank and vector rank, k=60. No score or like boost.
- Filters (tags, kind, since, publisher) apply before ranking.
- Tool: `search(q, tags?, kind?, since?, publisher?, limit=20)`, limit max 100.
- Returns links: title, url, publisher, published_at, score, summary, tags, and a `ts_headline` excerpt of about 300 chars.
- `tags()` returns slugs with article counts.
- Website search uses the same function.

### Rate limit
- In-process, per token: 20 calls/min, 500/day.
- Over the limit: ToolError with a retry hint.
- Code comment: move the counter to Postgres if the app runs more than one worker.

### Not deciding
- Embedding model swap (pick later by eval set).
- Chunking and RAG passages.
- Reranker.
- Watch/push for new matches.
- OAuth.
- Boosting by score or likes.
- Exposing stories in the views.

## Tasks

Backend tests: `cd backend && uv run pytest <path>`. Frontend: `bun run lint && bun run build`. Client: `scripts/generate-client.sh`.

### Phase 1: Hybrid search (website first, no auth needed)

- [x] Task 1: Full-text column on article
  - Criteria: migration adds generated `search_tsv` (english over title, summary, content; simple over title) and a GIN index. Additive only. Existing rows get it with no backfill script.
  - Verify: `alembic upgrade head` on the local db; `EXPLAIN` of a `@@` query uses the GIN index.
  - Deps: none. Files: `backend/migrations/versions/<new>.py`, `backend/app/core/db/article.py`. Size: S.

- [x] Task 2: Hybrid `search()` with filters and excerpt
  - Criteria: RRF (k=60) over full-text rank and vector rank. Filters tags, kind, since, publisher apply before ranking. Each row carries a `ts_headline` excerpt of about 300 chars. `limit` defaults to 20, max 100. `/articles/search` takes the new params. Client regenerated.
  - Verify: tests for keyword-only hit (e.g. `vLLM`), filter narrowing, limit cap, excerpt length. Manual: website search for "MCP" and "gpt-4o".
  - Deps: 1. Files: `backend/app/features/catalog/semantic_search.py` (rename to `search.py` if it reads better), `backend/app/features/catalog/model.py`, `backend/app/entry/api/articles.py`, its test, `frontend/src/client/*.gen.ts`. Size: M.
  - Built:
    - Module renamed to `search.py`.
    - Full-text rank is `ts_rank`, title weighted over summary over content.
    - The vector ranking scans every filtered row. The HNSW index picks its rows first and filters after, so a narrow filter would return almost nothing.
    - Search reads each ranking 100 deep before it fuses them.
    - On equal fused scores the keyword match goes first.
    - A tag whose name or slug matches counts as a keyword match (added after review).
    - Excerpts are plain text, no highlight markup.
    - On 6000 synthetic articles a search took 25-135 ms.

- [ ] Task 3: Eval set, old vs hybrid
  - Criteria: 20-30 real queries (from `analytics_event` if search is logged, else hand-written) in a small script that prints the old and hybrid top-10 side by side.
  - Verify: run it on the local db and read through the results; note the result in this plan.
  - Deps: 2. Files: `backend/scripts/search_eval.py`. Size: S.
  - Status: script written and run on the seeded sample rows only. The cloud session had no prod dump. Run it on a restored dump and note the result here.

### Checkpoint: Search

- [ ] Tests pass, frontend builds, hybrid is no worse than the old search on the eval set. Review before going on.

### Phase 2: Per-user MCP tokens

- [x] Task 4: Token model and API
  - Criteria: `mcp_token` table (user_id unique, token hash, created_at). `POST /users/me/mcp-token` creates or replaces and returns the raw token once. `DELETE` revokes it. `GET` says whether one exists, never the token.
  - Verify: tests for create, replace, revoke, and that the hash is never returned.
  - Deps: none. Files: `backend/app/core/db/<mcp_token>.py`, migration, `backend/app/features/audience/service.py`, `backend/app/entry/api/users.py`, tests. Size: M.
  - Built:
    - Tokens are free for every signed-in user. The user table has no Pro flag.
    - `user_id` is the primary key, and the row is deleted with the account.
    - The token is `agq_` plus 43 random characters, stored as a SHA-256 hash.
    - The token of an inactive account is refused.
    - `GET` also returns `created_at`.

- [x] Task 5: Token UI on the developers page
  - Criteria: signed-in users see create, copy (shown once), and revoke, plus the MCP config snippet for Claude Code. Signed-out users see a sign-in prompt.
  - Verify: frontend builds and lints. Manual: create, copy, revoke in the browser.
  - Deps: 4. Files: `frontend/src/features/developer-api/ui/*`, `frontend/src/routes/_layout/developers.tsx`, generated client. Size: M.
  - Built:
    - The snippet is the `claude mcp add` command with the token filled in.
    - Create, copy and revoke checked in headless Chromium against a local app.

- [x] Task 6: `user` scope in auth, internal tools hidden
  - Criteria: `SharedSecret` checks the shared tokens first, then hashes the token and looks it up in `mcp_token`. A match gets scope `user`. The tool list for `user` holds only `search`, `tags` and `sql_query`. Internal tools are not listed and are refused if called anyway.
  - Verify: tests that list tools and call one under each scope.
  - Deps: 4. Files: `backend/app/entry/mcp/auth.py`, `backend/app/entry/mcp/server.py`, `test_auth.py`, `test_server.py`. Size: M.
  - Built:
    - FastMCP can filter per token. Its `AuthMiddleware` hides tools from the list and refuses the call, with our check behind it.
    - The check is an allowlist, `USER_TOOLS` in `auth.py`, so a new tool is closed to `user` tokens until someone names it there.
    - `USER_TOOLS` was empty until Tasks 8 and 9 added `search`, `tags` and `sql_query`.
    - A test calls every other registered tool with a `user` token and expects a refusal.

- [x] Task 7: Rate limit per token
  - Criteria: 20 calls/min and 500/day per `user` token, in memory, with a ToolError that says when to retry. Internal tokens are not limited. Code comment for multi-worker.
  - Verify: tests with a fake clock.
  - Deps: 6. Files: `backend/app/entry/mcp/auth.py` or a new `rate_limit.py`, its test. Size: S.
  - Built:
    - Middleware in `rate_limit.py`. It counts per account, so replacing a token does not reset the count.
    - It counts calls the scope gate refuses too. Refused-for-limit calls are not counted.

### Phase 3: Public MCP tools

- [x] Task 8: `search` and `tags` tools
  - Criteria: `search` wraps Task 2's function and returns links with excerpts. `tags` returns slugs with counts. Docstrings explain the filters and how to chain `tags` into `search`.
  - Verify: tests through the MCP client.
  - Deps: 2, 6. Files: `backend/app/entry/mcp/search.py`, `tags.py`, `server.py`, tests. Size: S.
  - Built:
    - `search` also returns `id`, and `publisher` is a slug and a name, so a result can feed the `publisher` filter and `sql_query`.
    - `tags` also returns each tag's name.
    - The shared tokens reach both tools too.

- [x] Task 9: `public_api` views and public `sql_query`
  - Criteria: migration creates schema `public_api` with the views from the Spec. `deploy/sql-roles.sql` adds role `mcp_public` (USAGE plus SELECT on `public_api` only, read-only, 3s timeout, 5 connections). `sql_query` under `user` scope connects as `mcp_public`, and its docstring lists the views and columns.
  - Verify: tests that `content`, `score_reason`, `user` and the ledger are unreachable under `user` scope. Manual: run the role script on the local db.
  - Deps: 6. Files: migration, `deploy/sql-roles.sql`, `backend/app/core/settings.py`, `backend/app/entry/mcp/sql_query.py`, `.env.dev`, test. Size: M.
  - Built:
    - The role is in its own file, `deploy/sql-roles-public.sql`. `sql-roles.sql` cannot run twice, and this one can.
    - `publisher` has `slug` and no `url`. The table has no url column. `tag` also has `name`.
    - `kind` is text in both views.
    - Under `user` scope the tool refuses to run if its role can read `public.article`, so a wrong `MCP_PUBLIC_DB_USER` fails closed.
    - The tests create `mcp_public` from the script and try every table in `public`.
    - Role script run on the local db, twice.

### Checkpoint: Complete

- [ ] All tests pass, frontend builds.
- [ ] End to end: create a token in the browser, add it to Claude Code, then run `tags`, `search` and a `sql_query` join.
  - Done locally with a FastMCP client in place of Claude Code. Not done against prod.
- [ ] Prod: run `sql-roles.sql` on the box and set the `mcp_public` password in `/opt/agentique/.env`.

- [x] Task 10: Docs
  - Criteria: ADR for user MCP access (scopes, public views, excerpt-only content). Glossary entries for MCP token and `public_api`. The `server.py` instructions mention the user tools.
  - Deps: 8, 9. Files: `docs/adr/0020-*.md`, `docs/glossary.md`, `server.py`. Size: S.
  - Built: also a row in `deploy/README.md` and the tool list on the developers page.

### Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| A slow public query stalls the 2GB VPS | High | 3s timeout, 5 connections, rate limit |
| Generated tsvector migration locks `article` while it rewrites | Med | Table is small; run at low traffic |
| FastMCP can't filter the tool list per token | Med | Check in Task 6 first; fall back to list-time middleware |
| Hybrid ranks no better than the old search | Med | Task 3 eval before any public exposure |

### Open Questions

- The Spec says the role is created in a migration. The repo creates roles out of band in `deploy/sql-roles.sql` so no password lands in git. The plan follows the repo: views in a migration, the role in `sql-roles.sql`.
- The developers page sells a $10/mo Pro plan. Are MCP tokens free for every signed-in user, or a Pro feature?
