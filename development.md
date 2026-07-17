# Development

Only the database runs in Docker. Backend and frontend run natively.

## Requirements

- Docker (for the db)
- [uv](https://docs.astral.sh/uv/) — installs Python itself, no system Python needed
- [bun](https://bun.sh)
- a root `.env` file (gitignored) with at least: `PROJECT_NAME`, `SECRET_KEY`, `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`, `POSTGRES_SERVER=localhost`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

## The local loop

Start the db:

```bash
docker compose up -d
```

Run migrations + initial data (first time, and after pulling new migrations):

```bash
cd backend && uv run bash scripts/prestart.sh
```

Backend (http://localhost:8000, docs at /docs):

```bash
cd backend && uv run fastapi dev app/main.py
```

Frontend (http://localhost:5173):

```bash
cd frontend && bun run dev
```

Pipeline (manual run):

```bash
cd backend && uv run --env-file ../.env python -m pipeline.run
```

Backend tests:

```bash
cd backend && uv run bash scripts/tests-start.sh
```

## Database access

No Adminer anymore. Use either:

```bash
docker compose exec db psql -U <POSTGRES_USER> <POSTGRES_DB>
```

or any client (TablePlus etc.) against `localhost:5432` — the container publishes the port on loopback.

Careful: `docker compose down -v` deletes the db volume. Plain `down` is safe.

## env files

- root `.env` — backend + pipeline + compose config. The backend loads it via pydantic-settings (`env_file="../.env"`); the pipeline reads raw `os.environ`, hence `uv run --env-file`.
- `frontend/.env` — Vite-only vars (`VITE_API_URL`, `MAILCATCHER_HOST`). Kept separate on purpose: pointing Vite at the root `.env` would load secrets into the build process.

## Playwright (parked)

The e2e tests in `frontend/tests/` no longer run in CI. They still work locally against the native dev servers (`bunx playwright test` in `frontend/`), but expect them to rot.

## Pre-commit and linting

We use [prek](https://prek.j178.dev/) (modern pre-commit alternative). Config: `.pre-commit-config.yaml`.

Install the git hook (from `backend/`):

```bash
uv run prek install -f
```

Run manually on everything:

```bash
uv run prek run --all-files
```
