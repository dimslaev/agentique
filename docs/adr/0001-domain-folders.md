# 1. Domain folders, fixed per-folder file list

## Status

Accepted.

## Context

`backend/app/` read as "FastAPI template with a pipeline bolted on": `api/`,
`core/`, `models.py`, `crud.py` are framework layers, not domains. Nobody
could answer "where does X live" without already knowing the framework's
own folder conventions rather than agentique's.

## Decision

Organize `app/` as one folder per domain — `catalog/`, `audience/`,
`newsletter/`, `analytics/`, plus `platform/` for framework floor. A domain
folder contains only `models.py`, `service.py` (or a domain-named module
like `search.py`), `routes.py`, and `tests/`. A file whose name is not on
that list does not belong in a domain folder. `platform/` is the only home
for framework floor and is not a dumping ground — `shared/` and `common/`
stay forbidden, same as any module named `utils` (see ADR 3).

`pipeline/` keeps its own shape (`sources/`, `stages/`, `models.py`,
`run.py`) — it is a batch job, not a domain-organized service, and its
seams (fetch adapters, funnel stages) already scream what it does.

## Consequences

`ls app/` answers "what does this serve" without reading a line of code.
Adding a domain means adding a folder with the same four names, not
inventing a new layering convention. The fixed file list is a constraint,
not a suggestion: a module that doesn't fit `models.py` / `service.py` /
`routes.py` / `tests/` is a sign the domain boundary is wrong, not an
excuse to add a fifth file name.
