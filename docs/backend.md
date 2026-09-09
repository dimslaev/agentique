# Backend

## Requirements

- Docker (db only)
- [uv](https://docs.astral.sh/uv/) - Python package/env manager, installs Python too

## Running locally

- Needs a root `.env` (gitignored): `PROJECT_NAME`, `SECRET_KEY`, `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`, `POSTGRES_SERVER=localhost`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
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
- SQLModel models live with their domain: `app/catalog/models.py`, `app/audience/models.py`, `app/newsletter/models.py`, `app/analytics/models.py`, `pipeline/models.py` for the run record
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
- Alembic imports every model module in `app/alembic/env.py` - a new domain needs a line there or its tables are invisible to autogenerate

```bash
uv run alembic revision --autogenerate -m "Add column last_name to User model"
```

Commit the generated file under `app/alembic/versions/`, then:

```bash
uv run alembic upgrade head
```

## Email templates

- One transactional email: password recovery
- Template: `app/platform/email-templates/`, next to `app/platform/email.py`, which renders and sends it
- No MJML source - edit the HTML directly
