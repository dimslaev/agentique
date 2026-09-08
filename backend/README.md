# Backend

## Requirements

- Docker (for the db only)
- [uv](https://docs.astral.sh/uv/) for Python package and environment management — it installs Python itself too

## Running locally

Needs a root `.env` file (gitignored) with at least: `PROJECT_NAME`, `SECRET_KEY`,
`FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`, `POSTGRES_SERVER=localhost`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`. The backend loads it via
pydantic-settings (`env_file="../.env"`); the pipeline reads raw `os.environ`,
hence `uv run --env-file` below. `frontend/.env` is Vite-only (`VITE_API_URL`) and
kept separate on purpose — pointing Vite at the root `.env` would load secrets
into the build process.

```bash
docker compose up -d           # from the repo root: starts the db
cd backend
uv run bash scripts/prestart.sh   # migrations + initial data
uv run fastapi dev app/main.py
```

Pipeline (manual run):

```bash
cd backend && uv run --env-file ../.env python -m pipeline.run
```

## Pre-commit and linting

We use [prek](https://prek.j178.dev/) (modern pre-commit alternative). Config: `.pre-commit-config.yaml`.

```bash
uv run prek install -f       # install the git hook, from backend/
uv run prek run --all-files  # run manually on everything
```

## General Workflow

From `./backend/` install the dependencies with:

```console
$ uv sync
```

Then you can activate the virtual environment with:

```console
$ source .venv/bin/activate
```

Make sure your editor is using the correct Python virtual environment, with the interpreter at `backend/.venv/bin/python`.

SQLModel models live with the domain that owns them - `app/catalog/models.py`, `app/audience/models.py`, `app/newsletter/models.py`, `app/analytics/models.py`, and `pipeline/models.py` for the run record. API endpoints are in `./backend/app/api/`, CRUD (Create, Read, Update, Delete) utils in `./backend/app/crud.py`.

## VS Code

There are already configurations in place to run the backend through the VS Code debugger, so that you can use breakpoints, pause and explore variables, etc.

The setup is also already configured so you can run the tests through the VS Code Python tests tab.

## Backend tests

With the db up:

```console
$ uv run bash scripts/tests-start.sh
```

The tests run with Pytest, modify and add tests to `./backend/tests/`.

`tests-start.sh` waits for the db, then calls `scripts/test.sh` (pytest + coverage). Extra arguments are forwarded to pytest, e.g. stop on first error:

```console
$ uv run bash scripts/tests-start.sh -x
```

### Test Coverage

When the tests are run, a file `htmlcov/index.html` is generated, you can open it in your browser to see the coverage of the tests.

## Migrations

Make sure you create a "revision" of your models and that you "upgrade" your database with that revision every time you change them. As this is what will update the tables in your database. Otherwise, your application will have errors.

Alembic is already configured to import every model module in `app/alembic/env.py`. A new domain needs a line there, or its tables are invisible to autogenerate.

After changing a model (for example, adding a column), from `./backend/` create a revision:

```console
$ uv run alembic revision --autogenerate -m "Add column last_name to User model"
```

Commit the files generated under `./backend/app/alembic/versions/`, then apply the migration:

```console
$ uv run alembic upgrade head
```

## Email Templates

The one transactional email agentique sends is password recovery. Its rendered
template lives in `./backend/app/platform/email-templates/`, next to
`app/platform/email.py`, which renders and sends it. The MJML sources the
upstream template shipped were dropped - edit the HTML directly.

