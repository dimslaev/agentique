# 17. Three layers, one folder per feature

## Status

Accepted. Supersedes 1 and 4. Changes part of 7 and 8.

## Context

ADR 1 gave `app/` one folder per domain and left `pipeline/` beside it in its
own shape. The domains still imported each other. Every table sat in some
domain's `models.py`, and the pipeline and every domain read `Article` from
`catalog/models.py`. Routes in `audience/` called into `catalog` and
`newsletter`. `catalog/stories.py` used the embedding maths in
`pipeline/curation.py`, and the newsletter used the curation maths, the
ledger, `url_kind` and `SNIPPET_CAP`. The MCP tools reached into
`pipeline/fetching`.

Shared code had no single home. Some was in `app/platform/`, some in
`pipeline/`, and there were two engines: `app/platform/db.py` and
`pipeline/db.py`. Tests sat in a `tests/` folder in each domain (ADR 4), plus
`backend/tests/` for the pipeline, the scripts and the enum guard. The deploy
copied the whole checkout to the box.

## Decision

    app/main.py   wires entry.api and entry.mcp into one FastAPI app
    entry/        api/ mcp/ cli/            the ways in: HTTP, MCP, command line
    features/     catalog/ stories/ curation/ collect/ newsletter/ audience/ analytics/
    core/         db/ plus flat modules     tables, engine, shared mechanism

- **Three layers.** `entry/` composes features, features use `core/`, and
  imports only point down. One rule covers every case, so a reader can tell
  where a file goes from what it does.
- **Features never import each other.** When two features need the same
  thing, it moves to `core/`. When an API call spans features (sign-up
  creates a user and subscribes them), `entry/api/` composes them.
- **Every feature folder uses the same names.** `model.py` holds its own
  types, never tables. `service.py` holds the verbs entry calls, as
  `session` plus plain arguments. A file named after a `core` module
  (`audience/email.py`) adapts it. Other files are private helpers named
  after what they hold. A template sits beside its one consumer.
- **Tables live in `core/db/`, one module per table.** The table graph is
  shared. Foreign keys cross feature lines, and the migrations are already
  one history over the whole schema. Tables in a feature would force
  sideways imports. `core/db/__init__.py` imports every table module, so
  `SQLModel.metadata` is complete for autogenerate. `core/db/` also holds
  the one engine and the few table rules two features need
  (`like_counts_subquery`, `kind_from_url`). Queries one feature owns stay
  in that feature.
- **Shared mechanism is flat in `core/`.** `settings.py`, `http.py`,
  `extract.py`, `embedding.py` and the rest sit beside `db/`. A flat module
  imports stdlib, third-party packages and other flat modules, never
  `core.db`. There is no `shared/` folder, so ADR 3 needs no exception.
- **`entry/` has one file per router, one file per MCP tool, one file per
  command.** A route, a tool or a command is an adapter: parse the input,
  call a feature's `service`, shape the result. `entry/cli/` replaces
  `backend/scripts/`, `pipeline/run.py` and `pipeline/report.py`.
- **Tests sit beside their module as `test_<file>.py`.** No `tests/`
  folders. `backend/conftest.py` holds the shared fixtures, and
  `core/db/factories.py` the model factories.
- **import-linter enforces it.** `lint-imports` runs in pre-commit and in
  the test-backend workflow, with five contracts in `backend/pyproject.toml`:
  1. layers `app.main` > `app.entry` > `app.features` > `app.core`, exhaustive,
     so a new top-level module has to join a layer
  2. independence over `app.features.*`
  3. independence over `app.entry.api`, `app.entry.mcp`, `app.entry.cli`
  4. forbidden: the flat `app.core.*` modules never import `app.core.db`
  5. forbidden: entry reaches a feature only through its `service` and `model`
- **The deploy ships only what the box runs.** `deploy/rsync-filter` lists
  `backend/app/` without tests or factories, `backend/migrations/`,
  `backend/baml_client/`, the uv workspace files, `compose.yml`, `deploy/`
  and the built frontend. The sync deletes everything else on the box except
  `.env`, `.venv` and `.git`.

What changes in earlier ADRs:

- **1** is superseded. Domain folders with `models.py` / `service.py` /
  `routes.py` / `tests/` become feature folders with `model.py` /
  `service.py` and named helpers. Routes move to `entry/api/`. `platform/`
  becomes `core/`. `pipeline/` is no longer an exception. It becomes
  `features/collect/`, with its curation half in `features/curation/`.
- **4** is superseded. Tests still sit beside the code they test, but as
  `test_<file>.py` files next to the module, not in a `tests/` folder.
  `backend/tests/` is gone, and factories moved to `core/db/factories.py`.
  The frontend half of 4 is unchanged.
- **7** changes in part. There is one engine, in `core/db/engine.py`, and it
  takes the database URL from `Settings`, so the collect run builds Settings
  too. The box feeds both processes the same `.env`. The per-source knobs
  (IMAP, HN thresholds, the Tavily and GitHub keys, the proxy) still read
  `os.environ` in the module that uses them, and `deploy/README.md` still lists them.
- **8** changes in part. The stage-type chain splits at the queue. collect
  owns `RawItem` -> `Candidate` (`features/collect/model.py`). curation owns
  `Scored` -> `Summarized` -> `Persisted` (`features/curation/model.py`) and
  builds `Scored` from the ledger row the agent judged. `Scored` no longer
  subclasses `Candidate`, since that would import one feature into another.

## Consequences

`ls app/features/` lists what the backend does, and `ls` on one feature
lists its verbs, its types and its helpers. An import that breaks the rules
fails pre-commit and CI rather than review.

A rule two features share has to move to `core/` before either can use it.
That move gets its own commit.

The `stories` MCP tool (curation coverage) keeps its name although a
`stories/` feature now exists. Renaming it would change the curate rubric's
tools.

Contract 5 checks import paths, not names. A feature that re-exports a helper
from its `__init__.py` would let entry reach it without a failure.

The systemd units now run `app.entry.cli.*`. They are installed by hand, so
the deploy that changed `ExecStart` needed the units copied and
`daemon-reload` run before that night's timers.
