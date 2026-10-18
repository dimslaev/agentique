# Backend

## Requirements

- Docker (db only)
- [uv](https://docs.astral.sh/uv/) - Python package/env manager, installs Python too

## Running locally

- Needs a root `.env` (gitignored): `PROJECT_NAME`, `SECRET_KEY`, `FIRST_SUPERUSER`, `POSTGRES_SERVER=localhost`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- Backend loads it via pydantic-settings (`env_file="../.env"`)
- Pipeline reads raw `os.environ` directly, hence `--env-file` below
- `frontend/.env` is separate (Vite-only, `VITE_API_URL`) - keeps secrets out of the frontend build

```bash
docker compose up -d              # from repo root: starts the db
cd backend
uv run bash scripts/prestart.sh   # migrations + initial data
uv run fastapi dev app/main.py
```

Pipeline, manual run:

```bash
cd backend && uv run --env-file ../.env python -m pipeline.run
```

The run ends at pending candidates and publishes nothing — the curation agent
does that (ADR 9). Judge them, then send the night's report:

```bash
claude "/curate"                                        # from the repo root
cd backend && uv run --env-file ../.env python -m pipeline.report
```

`AGENTIQUE_MCP_TOKEN` must be the write token for `/curate` to publish anything;
with the read token the session can list candidates and settle none.

The weekly newsletter is the same shape: `claude "/newsletter"` reads the week
through the MCP server and drafts three issues as Resend broadcasts. It sends
nothing.

## Pre-commit and linting

Uses [prek](https://prek.j178.dev/). Config: `.pre-commit-config.yaml`.

```bash
uv run prek install -f       # install the git hook, from backend/
uv run prek run --all-files  # run manually on everything
```

## Setup

```bash
cd backend
uv sync
source .venv/bin/activate
```

- Point your editor's Python interpreter at `backend/.venv/bin/python`
- Tables live in `app/core/db/`, one module per table. API shapes stay in each domain's `models.py`
- Each domain folder holds its own `routes.py` and service module

VS Code: debugger and Python-tests-tab configs are already set up.

## Tests

With the db up:

```bash
uv run bash scripts/tests-start.sh
```

- Domain tests live in that domain's `tests/` folder (`app/catalog/tests/`, `app/audience/tests/`, ...)
- `backend/tests/` holds what belongs to no single domain: pipeline, schema-wide enum guard, ops scripts
- Shared fixtures: `backend/conftest.py`
- `tests-start.sh` waits for the db, then runs `scripts/test.sh` (pytest + coverage). Extra args forward to pytest:

```bash
uv run bash scripts/tests-start.sh -x
```

- Coverage report: `htmlcov/index.html`

## Migrations

- After changing a model, create a revision and apply it, or the schema and the app disagree
- `app/core/db/__init__.py` imports every table module. A new table module needs a line there or autogenerate can't see it
- Alembic's config is `[tool.alembic]` in `backend/pyproject.toml`

```bash
uv run alembic revision --autogenerate -m "Add column last_name to User model"
```

Commit the generated file under `migrations/versions/`, then:

```bash
uv run alembic upgrade head
```

## Email templates

- Two transactional emails: `welcome.html` on signup and `sign_in.html` on a sign-in request, both carrying a fresh sign-in link
- Templates: `app/core/email-templates/`, next to `app/core/email.py`, which renders and sends them
- The weekly newsletter issue: `weekly_issue.html` in the same folder, the site's wordmark over plain prose, rendered (autoescaped) and drafted by `app/newsletter/broadcast.py`
- No MJML source - edit the HTML directly
