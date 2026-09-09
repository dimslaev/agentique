# agentique

AI-powered article aggregation and intelligence feed. Fetches articles from configured sources, drops known/dead URLs, scores them with an LLM, extracts full content, categorizes and tags each piece, and stores vector embeddings for semantic search.

## How it works

A cron-scheduled pipeline fetches articles from configured sources and runs each batch through a sequence of BAML-powered steps: known/dead-URL filtering, LLM scoring, content extraction, categorization + tagging, vector embedding. Results are served via a FastAPI REST API and a React frontend.

The stack:

- db - PostgreSQL with pgvector, the only Docker container (`docker compose up -d`)
- backend - FastAPI, runs natively via uv (systemd service in production)
- pipeline - article pipeline, runs natively via uv (systemd timer, daily 04:00)
- frontend - React SPA, built to static files and served by Caddy in production

See [docs/backend.md](./docs/backend.md) and [docs/frontend.md](./docs/frontend.md) for the local loop, and [deploy/README.md](./deploy/README.md) for the VPS setup.

## Stack

- [FastAPI](https://fastapi.tiangolo.com) - Python backend API
- [BAML](https://docs.boundaryml.com) - structured LLM function definitions
- [PostgreSQL + pgvector](https://github.com/pgvector/pgvector) - article storage and vector search
- [model2vec](https://github.com/MinishLab/model2vec) - fast static embeddings
- [React](https://react.dev) + [Vite](https://vitejs.dev) + [Tailwind CSS](https://tailwindcss.com) - frontend
- [Docker Compose](https://docs.docker.com/compose/) - the database
- [Caddy](https://caddyserver.com) + systemd - production serving

## Docs

- [Backend](./docs/backend.md)
- [Frontend](./docs/frontend.md)
- [Glossary](./docs/glossary.md)
- [Product](./docs/product.md)
- [Deployment](./deploy/README.md)
