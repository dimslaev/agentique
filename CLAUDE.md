# agentique - instructions

## Chat tone 

Respond terse like smart caveman. All technical substance stay. Only fluff die
ACTIVE EVERY RESPONSE. No revert after many turns. No filler drift. Still active if unsure. Off only: "stop caveman"

## Docs 
- When asked for a plan, save it to `plans/<kebab-topic>.md`, without repeating in chat
- Keep markdown formatting down to minimum. Keep language accessible, concise and human readable. Use bullet points. 


## Client generation
- `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts`, `baml_client/` - must be generated after changes and committed

## Prod
- After `sudo`-touching `/opt/agentique/.env` (`chown ubuntu:agentique`, `chmod 640`) or `/var/lib/agentique/` (`chown -R agentique:agentique`), restore perms or agentique-backend/pipeline crash-loops