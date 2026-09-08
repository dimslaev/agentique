# Style

Rules a linter can enforce live in `backend/pyproject.toml` (ruff, mypy) and
`biome.json`, and fail CI. This file is the rest — style a linter cannot
express, enforced by review.

## Backend

- **A route handler is an adapter.** Parse input, call one domain function,
  shape the response. No SQL, no model loading, no branching business rules
  in a handler body.
- **Domain functions take an explicit `session` plus plain arguments and
  return domain types** — the same signature discipline as
  `step(session, articles) -> survivors` in the pipeline. No hidden
  globals.
- **Comments explain why, not what.** Well-named identifiers already say
  what the code does; a comment earns its place only for a hidden
  constraint, a subtle invariant, or a workaround for a specific bug.
- **Pipeline stage modules are verb-named** (`fetch`, `filter`, `score`,
  `persist`, `enrich`) — they are stages in a funnel. **Domain modules are
  noun-named** (`articles`, `likes`, `publishers`) — they are resources.
  This is a deliberate, permanent difference: forcing one naming scheme on
  both would make each half read wrong.
- **Constants live with their single consumer.** A constant read by exactly
  one module is an implementation detail of that module — it does not move
  to a shared file. A constant read by two or more modules is a real
  interface and lives at that seam (see `SNIPPET_CAP` in
  `pipeline/steps/filter.py` / `pipeline/steps/enrich.py` for the two-reader
  case). See the constants-vs-config discussion in the refactor plan for
  the reasoning.
- **`app/` holds the running service; `backend/scripts/` holds ops
  entrypoints.** A module that exists to be run by hand or by `prestart.sh` —
  waiting for the DB, creating the superuser, seeding — is an entrypoint, not
  part of the service, and lives in `backend/scripts/`. They are still
  type-checked (mypy and ty run over `backend/scripts` too); they are
  deliberately outside coverage's `source`, because pytest never runs them.
- **Config is different from constants.** Deployment-varying, env-provided
  values (database URL, API keys) live in one settings object
  (`app/platform/settings.py`). Tuning knobs compiled into the code
  (`SCORE_THRESHOLD`, `SNIPPET_CAP`) never move there.

## Frontend

- Route files (`routes/**/*.tsx`) stay one-liners — each imports one
  feature page component and nothing else. This is the one place
  file-based routing forces a structural exception, and it's a documented
  one.
- Feature code lives in `features/<name>/`, not in a generic `components/`.
  `ui/` (vendored shadcn) is left untouched — high churn, zero domain
  signal, not worth fighting the generator over.

## Repo-wide

- No module named `utils`, `helpers`, `common`, `shared`, or `misc` — see
  ADR 3. One documented exception: `frontend/src/lib/utils.ts`'s `cn()`,
  which is shadcn convention.
- A domain folder holds only `models.py`, `service.py` (or a domain-named
  module), `routes.py`, `tests/` — see ADR 1.
- Hide mechanism, never hide capability — see ADR 2.
- Tests colocate with the domain they test — see ADR 4.
