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
- **Pipeline stage modules are verb-named** (`fetch`, `filter`, `queue`,
  `persist`, `enrich`) — they are stages in a funnel. **Domain modules are
  noun-named** (`articles`, `likes`, `publishers`) — they are resources.
  This is a deliberate, permanent difference: forcing one naming scheme on
  both would make each half read wrong.
- **Constants live with their single consumer.** A constant read by exactly
  one module is an implementation detail of that module — it does not move
  to a shared file. A constant read by two or more modules is a real
  interface and lives at that seam (see `SNIPPET_CAP` in
  `app/core/embedding.py`, read by curation and by the newsletter, for the
  two-reader case). See the constants-vs-config discussion in the refactor plan for
  the reasoning.
- **Command-line entrypoints live in `app/entry/cli/`.** A module run by
  systemd, by `prestart.sh` or by hand (the nightly collect, the daily mail,
  waiting for the DB, seeding) calls feature verbs and sets the exit code,
  the way a route handler does for HTTP. Run it with
  `python -m app.entry.cli.<name>` from `backend/`. It is type-checked and
  counted in coverage like the rest of `app/`.
- **Config is different from constants.** Deployment-varying, env-provided
  values (database URL, API keys) live in one settings object
  (`app/core/settings.py`). Tuning knobs compiled into the code
  (`CANDIDATE_CAP`, `SNIPPET_CAP`) never move there.
- **The pipeline is the exception, on purpose.** It reads `os.environ` beside
  each consumer rather than through that settings object — see ADR 7. The index
  of what it reads lives in `deploy/README.md`; add a row there when you add a
  var.

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
