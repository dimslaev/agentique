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
| `sql-roles-public.sql` | creates `mcp_public`, the role a signed-in user's MCP `sql_query` logs in as. Run it after the deploy that adds the `public_api` views, then set its password to `MCP_PUBLIC_DB_PASSWORD` in `/opt/agentique/.env`. Safe to run again |
| `rsync-filter` | what the deploy copies to `/opt/agentique`, and what it never deletes there |

## Shape

- A push to `master` triggers `.github/workflows/deploy-production.yml`: build
  the frontend on a GitHub-hosted runner, then a self-hosted runner on the box
  rsyncs what the box runs, syncs the venv, runs migrations + prestart, and
  restarts the backend. Additive migrations only; rollback is `git revert` +
  push.
- The rsync copies only what `rsync-filter` lists: the backend's `app/`
  without tests, `migrations/`, the uv workspace files,
  `compose.yml`, `deploy/` and the built frontend. It deletes everything
  else in `/opt/agentique`, except `.env`, `.venv` and `.git`, which the
  deploy never sends. A file the box needs goes in the filter.
  `app/entry/cli/test_deploy_files.py` runs the filter and checks every path
  the units and the deploy job use.
- The units, the Caddyfile and `agentique-sql` are installed by hand. After
  a deploy that changes one, copy it from `/opt/agentique/deploy/` and run
  `sudo systemctl daemon-reload`. If an `ExecStart` path changed, the
  deploy has already deleted the old file. The backend then fails from the
  deploy's own restart until you copy its unit and restart it, and each
  timer fails the next time it fires. The deploy job doesn't install units
  because the runner can rewrite anything under `/opt/agentique`. Letting
  it install units with sudo would give it root.
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
  repo, invoking `/curate-articles`. Nothing about it is installed here: the box serves
  the MCP endpoint and holds the tokens it verifies, nothing more.
- **`AGENTIQUE_MCP_TOKEN` in that session must be the write token.** The MCP
  server serves both tokens at the same URL and the one in the header is what
  decides what the session can do: `MCP_TOKEN` reaches `search_articles`, `list_tags`,
  `sql_query`, `web_fetch` and `web_search`, `MCP_WRITE_TOKEN` every tool. A
  read token there gives you a session that does not see the curation tools.
- `MCP_WRITE_TOKEN` unset means nothing can be published at all — the same
  closed-by-default posture as `MCP_TOKEN`.

The routine's prompt lives on claude.ai, not here; this is its text, to paste
there when it changes. Everything else is in the skill.

```text
Run the `curate-articles` skill (`.claude/skills/curate-articles/SKILL.md`).
```

## Newsletter

The weekly issue is drafted by a second off-box routine, the same way as
curation: a scheduled task on claude.ai/code against this repo, with the same
write token, invoking `/draft-newsletter` (`.claude/skills/draft-newsletter/SKILL.md`).
It runs Fridays at 07:52 Europe/Zurich (`CRON_TZ=Europe/Zurich 52 7 * * 5`),
after that morning's curation and report, and reads the 7 days before it.

- It writes one draft, a grouped list of the week's best links, as a Resend
  broadcast to `RESEND_AUDIENCE_ID`. A person reads it in the Resend dashboard
  and sends it.
- Nothing in the code sends a broadcast. Sending is only ever done by hand.
- The issue is also a blog post (`frontend/content/blog/`). The routine saves
  the post and opens a PR; a person sends the draft in Resend and merges the
  PR. The routine needs push access to this repo for that.

The routine's prompt, to paste there when it changes:

```text
Run the `draft-newsletter` skill (`.claude/skills/draft-newsletter/SKILL.md`).
```

## Stories

The right rail's stories are kept by a third off-box routine, the same way as
curation and the newsletter: a scheduled task on claude.ai/code against this
repo, with the same write token, invoking `/update-stories`
(`.claude/skills/update-stories/SKILL.md`, ADRs 16 and 22). It runs daily at 06:17
Europe/Zurich (`CRON_TZ=Europe/Zurich 17 6 * * *`), after that morning's
curation and report.

- It reads the open stories and the last 14 days through `sql_query`, searches
  by keyword over 30 days, extends open stories, starts new ones and closes
  the ones quiet for 21 days, through `save_story` and `close_story`.
- It writes nothing else and commits nothing. A saved story is public at once
  once it has 3 articles from 2 publishers.
- A night it does not run, the rail stays as it was; the next run catches up
  over its 14-day window.

The routine's prompt, to paste there when it changes:

```text
Run the `update-stories` skill (`.claude/skills/update-stories/SKILL.md`).
```

## Discovery

Which publishers the nightly run polls is decided by a fourth off-box routine,
the same way as the others: a scheduled task on claude.ai/code against this
repo, with the same write token, invoking `/discover-publishers`
(`.claude/skills/discover-publishers/SKILL.md`, ADR 21). It runs daily at 06:47
Europe/Zurich (`CRON_TZ=Europe/Zurich 47 6 * * *`), after that morning's
curation and the stories routine.

- It switches off the feeds `review_publishers` lists to deactivate, and probes
  up to 30 inactive publishers, switching each one on or marking it off with
  a reason.
- It writes only `publisher` rows and commits nothing. A switched-on publisher
  is polled from the next nightly run.

The routine's prompt, to paste there when it changes:

```text
Run the `discover-publishers` skill (`.claude/skills/discover-publishers/SKILL.md`).
```

## Competitors

An off-box routine compares agentique with three competitors (AINews, Aligned News, AI/TLDR), the same way as the others: a scheduled task on claude.ai/code against this repo, with the same write token, invoking `/watch-competitors` (`.claude/skills/watch-competitors/SKILL.md`). It runs on Fridays at 16:00 Europe/Zurich (`CRON_TZ=Europe/Zurich 0 16 * * 5`).

- It reads each competitor's last-week top stories and matches them to `article` and `scored_url` through `sql_query`. It notes how far ahead or behind we were and why we rejected what we did.
- It writes `pending` candidates through `queue_candidate` (at most 10 a run) and inactive `publisher` rows through `add_publisher`. It switches a publisher on with `activate_publisher` only when the `discover-publishers` bar passes. Curation judges the candidates the next morning.
- It publishes its report and feature proposals to the `reports` branch (`docs/reports.md`) and nothing else.

The routine's prompt, to paste there when it changes:

```text
Run the `watch-competitors` skill (`.claude/skills/watch-competitors/SKILL.md`).
```

## Newsletter environment

Read by the backend through `app/core/settings.py`, with two exceptions that
read `os.environ`: `subscribe` (`app/features/newsletter/service.py`) reads
`RESEND_API_KEY` and `RESEND_AUDIENCE_ID`, and `send_mail`
(`app/core/email.py`), which sends the daily mail, reads `RESEND_API_KEY` and
`EMAILS_FROM_EMAIL`.

| Variable | Read by | Effect |
| --- | --- | --- |
| `RESEND_API_KEY` | `app/features/newsletter/broadcast.py`, `app/features/newsletter/service.py`, `app/core/email.py` | Unset: `draft_newsletter` refuses, naming it, signups are not synced to Resend, and the daily mail is only logged. |
| `RESEND_AUDIENCE_ID` | `app/features/newsletter/broadcast.py`, `app/features/newsletter/service.py` | The audience signups are synced to and the issue is broadcast to. |
| `EMAILS_FROM_EMAIL`, `EMAILS_FROM_NAME` | `app/features/newsletter/broadcast.py`, `app/core/email.py` (email only) | The issue's sender, and the daily mail's. |

## Pipeline environment

Read as raw `os.environ` beside each consumer (ADR 7), so they belong in
`/opt/agentique/.env` rather than in the settings object.

| Variable | Read by | Effect |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | `app/core/jev.py` | Jev, which classifies each newsletter link (sponsor, plumbing, on-topic, kind). Unset fails every link, so the newsletter channel yields nothing. |
| `PIPELINE_ALERT_EMAIL` | `app/core/email.py` | Where the daily mail goes (liveness, failing sources and feeds, what landed); falls back to `EMAILS_FROM_EMAIL`. |
| `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`, `IMAP_PORT` | `app/features/collect/newsletters.py` | The inbox the newsletter source reads. The first three are required by that source; the port defaults to 993. |
| `HN_MIN_POINTS`, `HN_MIN_COMMENTS`, `HN_GRACE_HOURS` | `app/features/collect/hn.py` | The HN traction gate: 10 points or 5 comments. A story under 6 hours old is held back for the next run. A URL from the creator skips the gate, and `HN_MIN_POINTS=0` turns it off. |
| `BLUESKY_HANDLE` | `app/features/collect/bluesky.py` | Optional. The Bluesky account whose follows the Bluesky source reads. Defaults to `agentique.ch`. |
| `TAVILY_API_KEY` | `app/core/web_search.py` | Search for the lab-watch source, the newsletter source and the `web_search` tool. |
| `GITHUB_TOKEN` | `app/core/github.py` | Optional. Raises the GitHub API rate limit for repo lookups. |
| `RESIDENTIAL_PROXY_URL` | `app/core/http.py` | Optional. A metered proxy, tried when a feed fetch or a page extraction is blocked direct. |
| `KDRIVE_API_TOKEN`, `KDRIVE_DRIVE_ID`, `KDRIVE_BACKUP_DIR`, `KDRIVE_BACKUP_KEEP` | `app/entry/cli/backup_db.py` | Where the nightly dump goes. The dir defaults to `/Private/agentique-db`, and 14 dumps are kept. |
