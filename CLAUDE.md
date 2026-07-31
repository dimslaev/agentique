# agentique - instructions

## Chat tone 

Respond terse like smart caveman. All technical substance stay. Only fluff die
ACTIVE EVERY RESPONSE. No revert after many turns. No filler drift. Still active if unsure. Off only: "stop caveman"

## Docs 
- When asked for a plan, save it to `plans/<kebab-topic>.md`, without repeating in chat
- Keep markdown formatting down to minimum. Keep language accessible, concise and human readable. Use bullet points. 


## Client generation
- `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts`, `baml_client/` - must be generated after changes and committed

## Local / cloud-session db
- `scripts/restore-db.sh` - starts the `db` container and restores the newest dump in `dumps/`. Always use the latest dump; never hand-pick an older file
- Credentials are in committed `.env.dev` (local throwaway only), copied to `.env` when missing. `POSTGRES_USER` must stay `postgres`
- Read and mutate freely - it is a local copy, not prod. `scripts/dump-prod-db.sh` refreshes it from prod (local only, needs ssh)

## Prod
- After `sudo`-touching `/opt/agentique/.env` (`chown ubuntu:agentique`, `chmod 640`) or `/var/lib/agentique/` (`chown -R agentique:agentique`), restore perms or agentique-backend/pipeline crash-loops

## Prod DB/VPS access
- Detect env first: `test -f ~/.ssh/agentique && echo local || echo cloud`
- Local (key present): `ssh agentique-prod "..."` direct
- Cloud (no key): `gh workflow run prod-sql.yml -f sql="..." -f mode=read|write` (write also needs `-f confirm=WRITE`)
- Same rule for any prod SQL, not just VPS shell access