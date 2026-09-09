# Frontend

Built with [Vite](https://vitejs.dev/), [React](https://reactjs.org/), [TypeScript](https://www.typescriptlang.org/), [TanStack Query](https://tanstack.com/query), [TanStack Router](https://tanstack.com/router), [Tailwind CSS](https://tailwindcss.com/).

## Requirements

- [Bun](https://bun.sh/) (recommended) or Node.js

## Quick start

```bash
bun install
bun run dev
```

- Open http://localhost:5173/
- See `package.json` for other scripts
- Production: not a server - CI runs `bun run build`, Caddy serves `dist/` as static files (see [../deploy/README.md](../deploy/README.md))

## Generate client

Automatic:

- Activate the backend virtual environment
- From the repo root: `bash ./scripts/generate-client.sh`
- Commit the changes

Manual:

- Start the backend: `cd backend && uv run fastapi dev app/main.py`
- Download `http://localhost:8000/api/v1/openapi.json` to `frontend/openapi.json`
- Run `bun run generate-client`
- Commit the changes

Re-run this whenever the backend's OpenAPI schema changes.

## Remote API

Set `VITE_API_URL` to point the frontend at a different backend, e.g. in `frontend/.env`:

```env
VITE_API_URL=https://api.my-domain.example.com
```

## End-to-end tests (Playwright, parked)

- `frontend/tests/` - no longer runs in CI, runs locally only
- Start the db, backend, and this dev server, then:

```bash
bunx playwright test
```

- UI mode: `bunx playwright test --ui`
- Docs: https://playwright.dev/docs/intro
