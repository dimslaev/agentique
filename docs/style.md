# Style

Rules a linter can enforce live in `backend/pyproject.toml` (ruff, mypy,
import-linter) and `biome.json`, and fail CI. This file holds the rest, the
style a linter cannot express, enforced by review.

## Backend

- **Three layers, imports point down.** `app/entry/` (api, mcp, cli) calls
  `app/features/`, and features call `app/core/`. Features never import each
  other, and api, mcp and cli never import each other. `lint-imports`
  enforces this (ADR 17).
- **A feature folder uses the same file names.** `model.py` for its own
  types (no tables), `service.py` for the verbs entry calls, a file named
  after a `core` module for the adapter over it (`audience/email.py`), and
  private helpers named after what they hold (`facets.py`, `coverage.py`).
  Entry imports a feature's `service` and `model` only.
- **Tables live in `app/core/db/`, one module per table.** A query only one
  feature runs stays in that feature. A rule two features need on a table
  goes beside the table (`like_counts_subquery` in `like.py`).
- **Shared mechanism is flat in `app/core/`.** A flat `core` module imports
  stdlib, third-party packages and other flat `core` modules, never
  `core.db`. When a second feature needs something from the first, it
  moves to `core/`.
- **A route handler, an MCP tool and a command are adapters.** Parse input,
  call feature verbs, shape the response or set the exit code. When one call
  spans two features (sign-up creates a user and subscribes them), the
  handler composes them; the features don't import each other. No SQL, no
  model loading, no branching business rules in their bodies. One file per
  router in `entry/api/`, per tool in `entry/mcp/`, per command in
  `entry/cli/`.
- **Feature verbs take an explicit `session` plus plain arguments and return
  domain types.** No hidden globals.
- **Comments explain why, not what.** Well-named identifiers already say
  what the code does; a comment earns its place only for a hidden
  constraint, a subtle invariant, or a workaround for a specific bug.
- **collect's stage modules are verb-named** (`fetch`, `filter`, `queue`),
  because they are stages in a funnel. **Other modules are noun-named**
  (`facets`, `publishers`, `coverage`), because they are resources. One
  naming scheme for both would make each half read wrong.
- **Constants live with their single consumer.** A constant read by exactly
  one module is an implementation detail of that module and does not move
  to a shared file. A constant read by two or more features is an interface
  and lives in `core` (`SNIPPET_CAP` in `app/core/embedding.py`, read by
  curation and by the newsletter).
- **Command-line entrypoints live in `app/entry/cli/`.** A module run by
  systemd, by `prestart.sh` or by hand (the nightly collect, the daily mail,
  waiting for the DB, seeding) calls feature verbs and sets the exit code.
  Run it with `python -m app.entry.cli.<name>` from `backend/`. It is
  type-checked and counted in coverage like the rest of `app/`.
- **Config is different from constants.** Deployment-varying, env-provided
  values (database URL, API keys) live in one settings object
  (`app/core/settings.py`). Tuning knobs compiled into the code
  (`CANDIDATE_CAP`, `SNIPPET_CAP`) never move there.
- **Per-source knobs are the exception, on purpose.** The IMAP account, the
  HN thresholds, the Tavily and GitHub keys and the proxy are read from
  `os.environ` in the module that uses them (ADR 7). The index of what is read
  lives in `deploy/README.md`; add a row there when you add a var.
- **Tests sit beside their module** as `test_<file>.py`. No `tests/`
  folders. Shared fixtures are in `backend/conftest.py`, model factories in
  `app/core/db/factories.py` (ADR 17).

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
  ADR 3. Two documented exceptions: `frontend/src/shared/lib/utils.ts`'s `cn()`,
  which is shadcn convention, and `frontend/src/shared/`, the FSD layer.
- Hide mechanism, never hide capability — see ADR 2.
- Tests sit beside the code they test. Backend: see ADR 17. Frontend: see
  ADR 4.
