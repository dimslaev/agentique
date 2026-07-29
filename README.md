# agentique

AI-powered article aggregation and intelligence feed. Fetches articles from configured sources, drops known/dead URLs, scores them with an LLM, extracts full content, categorizes and tags each piece, and stores vector embeddings for semantic search.

## How it works

A cron-scheduled pipeline fetches articles from configured sources and runs each batch through a sequence of BAML-powered steps: known/dead-URL filtering, LLM scoring, content extraction, categorization + tagging, and vector embedding. Results are served via a FastAPI REST API and a React frontend.

The stack:

- `db` — PostgreSQL with pgvector, the only Docker container (`docker compose up -d`)
- backend — FastAPI, runs natively via uv (systemd service in production)
- pipeline — article pipeline, runs natively via uv (systemd timer, daily 04:00)
- frontend — React SPA, built to static files and served by Caddy in production

See [development.md](./development.md) for the local loop and [deployment.md](./deployment.md) for the VPS setup.

## Stack

- [FastAPI](https://fastapi.tiangolo.com) — Python backend API
- [BAML](https://docs.boundaryml.com) — structured LLM function definitions
- [PostgreSQL + pgvector](https://github.com/pgvector/pgvector) — article storage and vector search
- [model2vec](https://github.com/MinishLab/model2vec) — fast static embeddings
- [React](https://react.dev) + [Vite](https://vitejs.dev) + [Tailwind CSS](https://tailwindcss.com) — frontend
- [Docker Compose](https://docs.docker.com/compose/) — the database
- [Caddy](https://caddyserver.com) + systemd — production serving

## Docs

- [Backend](./backend/README.md)
- [Frontend](./frontend/README.md)
- [Deployment](./deployment.md)
- [Development](./development.md)

## Upstream

Started as a fork of [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template). The fork is cut — upstream is no longer merged. [CHANGES.md](./CHANGES.md) is frozen as the historical record of divergences.
