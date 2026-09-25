# deploy/

How agentique runs in production. Docker runs only the database
(`compose.yml` at the repo root); everything else is native.

## Pieces

| File | Role |
| --- | --- |
| `Caddyfile` | TLS + static frontend + reverse proxy to the API (`/etc/caddy/Caddyfile`) |
| `agentique-backend.service` | FastAPI under systemd, 2 workers, bound to `127.0.0.1:8000` |
| `agentique-pipeline.service` + `.timer` | the article pipeline, one run daily at 04:00 |
| `agentique-report.service` + `.timer` | the night's one report email at 06:00 |
| `agentique-backup.service` + `.timer` | nightly DB dump to off-box storage at 03:30 |
| `agentique-sql` | run SQL against the prod DB from stdin, inside the `db` container |
| `sql-roles.sql` | one-time: creates the read-only and read/write login roles `agentique-sql` uses |

## Shape

- A push to `master` triggers `.github/workflows/deploy-production.yml`: build
  the frontend on a GitHub-hosted runner, then a self-hosted runner on the box
  rsyncs the source, syncs the venv, runs migrations + prestart, and restarts
  the backend. Additive migrations only; rollback is `git revert` + push.
- The pipeline needs no restart — the timer starts a fresh process each run.
- The night runs in three steps an hour apart: 04:00 the pipeline queues
  candidates, 05:00 the agent judges them, 06:00 the report goes out. The box
  owns the first and the last as separate timers; the agent runs off-box (see
  Curation). A failure in one does not silence the others — a night the agent
  never ran still gets a report, and that report says nothing landed.
- Nothing is lost when the agent does not run: candidates stay pending and the
  next session reads them alongside the new ones.
- Break-glass writes are `agentique-sql` over ssh, run by hand: it pipes the
  statement into `psql` as `agentique_rw`, with that role's statement, lock and
  idle timeouts. There is no CI path for it — prefer a migration, and reach for
  this only when nothing else will fix prod.
- Postgres is published on loopback only. `agentique_rw` is passwordless, so it
  can only ever be reached through the local socket (`docker exec`), never over
  the network. `agentique_ro` has a password so it can also be used over
  loopback TCP; it is SELECT-only, read-only by default, and cannot see the
  `user` table at all.

## Config

Runtime config is a single `.env` on the box, hand-written once and never
touched by CI. It must set `ENVIRONMENT=production` and
`POSTGRES_SERVER=localhost`. `.env.dev` at the repo root lists the variables
with throwaway local values; `deploy/README` in a fork should document whatever
subset a given deployment actually needs.

## Curation

The judge is a Claude Code session, not an LLM call inside the pipeline (ADR 9).
It reads pending candidates through the MCP server this same box serves.

- The session runs off-box, as a scheduled task on claude.ai/code against this
  repo, invoking `/curate`. Nothing about it is installed here: the box serves
  the MCP endpoint and holds the tokens it verifies, nothing more.
- **`AGENTIQUE_MCP_TOKEN` in that session must be the write token.** The MCP
  server serves both tokens at the same URL and the one in the header is what
  decides what the session can do: `MCP_TOKEN` reaches `sql_query`, `web_fetch`
  and `web_search`, `MCP_WRITE_TOKEN` also reaches `approve` and `reject`. A
  read token there gives you a session that reads every candidate and publishes
  none.
- `MCP_WRITE_TOKEN` unset means nothing can be published at all — the same
  closed-by-default posture as `MCP_TOKEN`.

The routine's prompt lives on claude.ai, not here; this is its text, to paste
there when it changes. Keep the steps in step with `SKILL.md`.

```text
Run the agentique nightly curation session.

Invoke the `curate` skill (`.claude/skills/curate/SKILL.md` in this repo) and follow it end to end:

1. `list_candidates()` on the agentique MCP server for everything the 04:00 pipeline queued, passing `next_offset` back as `offset` until it is null — read every page before settling any candidate. `vocabulary()` once for the labels.
2. Triage on title and snippet. Reject what triage settles in one `reject_many`.
3. Call `stories()` once, to see which candidates are one story and which the feed already carries.
4. Read page one of `get_content(url)` for everything past triage; read on to the end for anything you approve. `check_link` the repo or model an approval rests on. Use `web_fetch` only when the stored text is empty, a teaser or cut short, and the web tools otherwise only where the skill's "Looking further" section says to.
5. Call `similar(url)` before each approval, so a retelling of a story we already carry is caught.
6. Settle every candidate with `approve(url, score, reason, summary, categories, kind, tags)`, `reject(url, score, reason)` or `reject_many`. Apply the daily caps at the end, over the whole night.

Do not stop partway — a candidate left pending waits another day. Do not edit files or commit anything; this session reads and curates, nothing else.

If `list_candidates` comes back with "This tool needs the curation token", the environment's AGENTIQUE_MCP_TOKEN is the read token rather than MCP_WRITE_TOKEN. Stop and say so plainly — do not try to work around it.

Finish with a short report: how many approved, how many rejected, how many web searches, fetches and check_link calls you made, and anything that blocked you.
```

## Pipeline environment

Read as raw `os.environ` beside each consumer (ADR 7), so they belong in
`/opt/agentique/.env` rather than in the settings object.

| Variable | Read by | Effect |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | `pipeline/jev.py` | Jev, which classifies each newsletter link (sponsor, plumbing, on-topic, kind). Unset fails every link, so the newsletter channel yields nothing. |
| `PIPELINE_ALERT_EMAIL` | `pipeline/report.py` | Where the daily mail goes (liveness, failing sources and feeds, what landed); falls back to `EMAILS_FROM_EMAIL`. |
