# 5. Stop merging upstream

## Status

Accepted. Decided during the docker-db-only migration; this ADR is that
decision written down for the first time.

## Context

Agentique started as a fork of
[fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template).
While the fork tracked upstream, its full Docker Compose stack (backend
container, frontend container, proxy, mailcatcher) stayed intact, because
diverging from it would have made future `git merge` from upstream
progressively harder. That constraint shaped a lot of early structure —
generic `app/` naming, template routes kept even when unused, docs
describing infrastructure agentique doesn't run.

The docker-db-only migration moved deployment to one VPS running Postgres
in Docker and everything else (backend, pipeline, frontend) as native
processes under uv/Bun/systemd/Caddy (see ADR 6). That migration is
incompatible with continuing to merge upstream's Compose-centric changes,
but the decision to actually stop merging was never written down anywhere
— it was implied by the migration rather than stated.

## Decision

The fork is cut. Agentique does not merge from
`fastapi/full-stack-fastapi-template` again. `CHANGES.md` is frozen as the
historical record of where this fork diverged from upstream before the
cut; it stops being a living changelog.

## Consequences

This unblocks restructuring `app/` freely — domain folders, renamed
modules, dissolved `api/`/`core/` layers — none of which would have been
worth doing if every future upstream merge had to be re-reconciled against
it. It also means agentique now owns fixing or updating anything inherited
from the template (auth scaffolding, migration tooling, project layout)
itself; there's no more free ride on upstream's improvements.
