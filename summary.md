# agentique

AI-powered article aggregation. Fetches, scores, categorizes, and embeds articles from sources via FastAPI and React.

## How it works

Daily pipeline filters dead URLs, scores articles with LLMs, extracts content, categorizes, tags, and stores embeddings.

## Stack

- FastAPI, PostgreSQL + pgvector, React + Vite + Tailwind CSS, Docker Compose, Caddy

## Docs

- [docs/backend.md](https://docs.boundaryml.com)
- [docs/frontend.md](https://react.dev)
- [Glossary](https://github.com/pgvector/pgvector)
- [Deployment](./deploy/README.md)