# Backend

## Requirements

- Docker (db only)
- [uv](https://docs.astral.sh/uv/) - Python package/env manager, installs Python too

## Running locally

- Needs a root `.env` (gitignored): `PROJECT_NAME`, `SECRET_KEY`, `FIRST_SUPERUSER`, `POSTGRES_SERVER=localhost`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- Backend loads it via pydantic-settings (`env_file="../.env"`)
- The per-source knobs (IMAP, HN thresholds, API keys) are read from raw `os.environ`, hence `--env-file` below
- `frontend/.env` is separate (Vite-only, `VITE_API_URL`) - keeps secrets out of the frontend build

```bash
docker compose up -d              # from repo root: starts the db
cd backend
uv run bash app/entry/cli/prestart.sh   # migrations + initial data
uv run fastapi dev app/main.py
```

The nightly collect, run by hand:

```bash
cd backend && uv run --env-file ../.env python -m app.entry.cli.collect
```

The run ends at pending candidates and publishes nothing — the curation agent
does that (ADR 9). Judge them, then send the night's report:

```bash
claude "/curate"                                        # from the repo root
cd backend && uv run --env-file ../.env python -m app.entry.cli.report
```

`AGENTIQUE_MCP_TOKEN` must be the write token for `/curate` to publish anything;
with the read token the session can list candidates and settle none.

The weekly newsletter is the same shape: `claude "/newsletter"` reads the week
through the MCP server and drafts three issues as Resend broadcasts. It sends
nothing.

## Pre-commit and linting

Uses [prek](https://prek.j178.dev/). Config: `.pre-commit-config.yaml`.

```bash
uv run prek install -f       # install the git hook
uv run prek run --all-files  # run manually on everything
```

- Runs ruff (lint and format) on every Python file, `mypy --strict` and `ty` over `backend/app`, typos, biome and the banned-module-names check
- Runs `lint-imports`, which checks the five import contracts in `backend/pyproject.toml` (ADR 17). The test-backend workflow runs it too
- Regenerates the frontend client when anything under `backend/` changes

## Setup

```bash
uv sync
source .venv/bin/activate
```

- uv workspace: the root `pyproject.toml` lists `backend/` as its one member, so the venv is the root `.venv`
- Point your editor's Python interpreter at `.venv/bin/python`

## Layout

- `app/main.py` - the FastAPI app: the routers, then the MCP server at `/mcp`
- `app/entry/` - the ways in: `api/` one file per router, `mcp/` one file per tool, `cli/` one file per command
- `app/features/` - one folder per feature: catalog, stories, curation, collect, newsletter, audience, analytics. Each has `model.py` and `service.py`
- `app/core/` - `db/` (the tables, one module each, and the engine) plus flat shared modules (`settings.py`, `http.py`, `extract.py`, `embedding.py`, ...)
- Imports point down, entry to features to core, and features never import each other (ADR 17)

## Tests

With the db up:

```bash
cd backend
uv run bash ../scripts/tests-start.sh
```

- Each test sits beside its module as `test_<file>.py` (`app/features/catalog/service.py` and `test_service.py`). No `tests/` folders
- Shared fixtures: `backend/conftest.py`. Model factories: `app/core/db/factories.py`
- `tests-start.sh` waits for the db, then runs `scripts/test.sh` beside it (pytest + coverage). An argument becomes the coverage report's title, not a pytest flag:

```bash
uv run bash ../scripts/tests-start.sh "my branch"
```

- Coverage report: `htmlcov/index.html`. Test files, `conftest.py` and `factories.py` are left out of the count

## Migrations

- After changing a model, create a revision and apply it, or the schema and the app disagree
- `app/core/db/__init__.py` imports every table module. A new table module needs a line there or autogenerate can't see it
- Alembic's config is `[tool.alembic]` in `backend/pyproject.toml`. Revisions are in `backend/migrations/versions/`

From `backend/`:

```bash
uv run alembic revision --autogenerate -m "Add column last_name to User model"
```

Commit the generated file under `migrations/versions/`, then:

```bash
uv run alembic upgrade head
```

## Email templates

- Two transactional emails: `welcome.html` on signup and `sign_in.html` on a sign-in request, both carrying a fresh sign-in link
- They sit in `app/features/audience/`, beside `email.py`, which builds them and sends them through `app/core/email.py`
- The weekly newsletter issue: `app/features/newsletter/weekly_issue.html`, the site's wordmark over plain prose, rendered (autoescaped) and drafted by `broadcast.py` beside it
- No MJML source - edit the HTML directly
