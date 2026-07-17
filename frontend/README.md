# Frontend

The frontend is built with [Vite](https://vitejs.dev/), [React](https://reactjs.org/), [TypeScript](https://www.typescriptlang.org/), [TanStack Query](https://tanstack.com/query), [TanStack Router](https://tanstack.com/router) and [Tailwind CSS](https://tailwindcss.com/).

## Requirements

- [Bun](https://bun.sh/) (recommended) or [Node.js](https://nodejs.org/)

## Quick Start

```bash
bun install
bun run dev
```

* Then open your browser at http://localhost:5173/.

Check the file `package.json` to see other available options.

In production the frontend is not a server at all — CI runs `bun run build` and Caddy serves the resulting `dist/` as static files (see [../deployment.md](../deployment.md)).

## Generate Client

### Automatically

* Activate the backend virtual environment.
* From the top level project directory, run the script:

```bash
bash ./scripts/generate-client.sh
```

* Commit the changes.

### Manually

* Start the backend (`cd backend && uv run fastapi dev app/main.py`).

* Download the OpenAPI JSON file from `http://localhost:8000/api/v1/openapi.json` and copy it to a new file `openapi.json` at the root of the `frontend` directory.

* To generate the frontend client, run:

```bash
bun run generate-client
```

* Commit the changes.

Notice that everytime the backend changes (changing the OpenAPI schema), you should follow these steps again to update the frontend client.

## Using a Remote API

If you want to use a remote API, you can set the environment variable `VITE_API_URL` to the URL of the remote API. For example, you can set it in the `frontend/.env` file:

```env
VITE_API_URL=https://api.my-domain.example.com
```

Then, when you run the frontend, it will use that URL as the base URL for the API.

## End-to-End Testing with Playwright (parked)

The e2e tests in `frontend/tests/` no longer run in CI. They still run locally against the native dev servers: start the db, backend and frontend (see [../development.md](../development.md)), then:

```bash
bunx playwright test
```

You can also run your tests in UI mode to see the browser and interact with it running:

```bash
bunx playwright test --ui
```

For more information on writing and running Playwright tests, refer to the official [Playwright documentation](https://playwright.dev/docs/intro).
