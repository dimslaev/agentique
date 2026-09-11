# agentique - instructions

## Docs
- `docs/glossary.md` - the words the code uses (Publisher, Article, Source, Trust, Score, Traction, Run, ...)
- `docs/adr/` - decisions made and why, written once, never edited
- `docs/style.md` - coding conventions a linter can't enforce
- `docs/product.md` - what agentique is, for anyone picking up work here
- `deploy/README.md` - how it runs in production
- `.ignored/plans/` - proposed work in progress, deleted once shipped (gitignored)
- When asked for a plan, save it to `.ignored/plans/<kebab-topic>.md`. Don't repeat it in chat.
- Minimal markdown formatting, plain concise language, short bullet points.

## Chat tone
- Terse, plain language. No metaphors.
- Keep all technical substance, cut filler.
- Active every response, no drift back to verbose over time.
- Stays active even if unsure.

## Git
- Commit message: subject line only, no body/description.
- Conventional commit type, no scope: `feat: auth something`, not `feat(auth): something`.
- PR/MR title: exactly the same format as the commit subject.
- Branch name: same, but slash instead of `: ` and dashes instead of spaces - `feat/auth-something`.

## Client generation
- `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts`, `baml_client/` are generated. Regenerate after changes and commit them.

## Local db
- `scripts/restore-db.sh` starts the `db` container and restores the newest dump in `.ignored/dumps/`. Always use the latest dump, never an older one.
- Credentials are in committed `.env.dev` (local throwaway only), copied to `.env` when missing. `POSTGRES_USER` must stay `postgres`.
- Read and mutate freely. It's a local copy, not prod.

## MCP tools
- `.mcp.json` connects to the `agentique` MCP server (`backend/app/mcp/`), exposing `sql_query` (read-only prod Postgres), `web_fetch`, `web_search`.
- Don't use these unless the user specifically asks for them. Prefer local tools (Read, Grep, the local db) for everything else.
