# agentique - instructions

## Docs
- `docs/glossary.md` - the words the code uses (Publisher, Article, Source, Trust, Score, Traction, Run, ...)
- `docs/adr/` - decisions made and why, written once, never edited
- `docs/style.md` - coding conventions a linter can't enforce
- `README.md` - what agentique is and how its parts work, for anyone picking up work here
- `deploy/README.md` - how it runs in production
- `docs/reports.md` - the `reports` branch the business routines write their proposals to
- `.ignored/plans/` - proposed work in progress, deleted once shipped (gitignored)
- When asked for a plan, save it to `.ignored/plans/<kebab-topic>.md`. Don't repeat it in chat.
- Minimal markdown formatting, plain concise language, short bullet points.

## Chat tone
- Terse, plain language. No metaphors.
- Keep all technical substance, cut filler.
- Active every response, no drift back to verbose over time.
- Stays active even if unsure.
- No AI tells: no em dashes, filler, hedging, chatbot phrases, fancy words where plain ones work.

## After changes
- After a round of changes, run the `deslop` skill on the code and `unslop` on any prose written.

## Git
- Commit straight to master. Don't create a branch or open a PR unless asked or you're running in cloud.
- Commit message: subject line only, no body/description.
- Conventional commit type, no scope: `feat: auth something`, not `feat(auth): something`.
- PR/MR title: exactly the same format as the commit subject.
- Branch name: same, but slash instead of `: ` and dashes instead of spaces - `feat/auth-something`.

## Client generation
- `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts` are generated. Regenerate after changes and commit them.

## Local db
- `scripts/restore-db.sh` starts the `db` container and restores the newest dump in `.ignored/dumps/`. Always use the latest dump, never an older one.
- Credentials are in committed `.env.dev` (local throwaway only), copied to `.env` when missing. `POSTGRES_USER` must stay `postgres`.
- Read and mutate freely. It's a local copy, not prod.
- Cloud sessions have no Docker and no dump. The `agentique` environment's setup script installs Postgres 16 with pgvector and creates a migrated `app` db with the sample articles. Start it with `pg_ctlcluster 16 main start`.

## MCP tools
- `.mcp.json` connects to the `agentique-admin` MCP server (`backend/app/entry/mcp/`), named apart from the `agentique` entry the /connect page has users add, so a user-scope one isn't shadowed here. With the read token it exposes `search_articles`, `list_tags`, `sql_query` (read-only prod Postgres), `web_fetch`, `web_search`.
- Every other tool needs the write token, and many write to prod: they publish articles, draft the newsletter in Resend, edit the right rail, or switch which publishers prod polls. The skills that use them: `curate-articles`, `draft-newsletter`, `update-stories`, `discover-publishers` in `.claude/skills/`.
- Don't use any of these unless the user specifically asks for them. Prefer local tools (Read, Grep, the local db) for everything else.

## Curation
- The pipeline does not judge articles. It drops known URLs, queues the rest as candidates (`RejectStage.pending`), and a Claude Code session decides each one - see `docs/adr/0009-agent-curation.md` and `docs/adr/0011-collector-judge-split.md`.
- The agent's rubric is `.claude/skills/curate-articles/SKILL.md`. Changing it means re-running the regression set beside it before it goes back on the schedule.
