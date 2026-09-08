# 4. Tests colocate with their domain

## Status

Accepted.

## Context

A parallel `backend/tests/` tree mirroring `backend/app/` makes every
question about a domain two lookups instead of one, and the mirror rots
silently: `backend/tests/` already carried stale `__pycache__` for an
`item.py` that no longer exists, and a `tests/crud/` folder is orphaned the
moment `crud.py` is dissolved into domain modules.

## Decision

Tests live inside the domain they test: `app/catalog/tests/`,
`app/audience/tests/`, and so on — one `tests/` folder per domain, next to
that domain's `models.py` / `service.py` / `routes.py`. Shared fixtures
stay in one root `backend/conftest.py`; pytest walks up the tree, so
per-domain tests get them for free without any per-domain conftest. Model
factories (`tests/utils/user.py`, `tests/utils/article.py` today) move to
the domain that owns the model — a factory is knowledge about a model and
belongs with it.

Frontend unit and component tests colocate in `features/<name>/` the same
way. Playwright end-to-end tests are the one documented exception: a
signup-then-like journey spans two features, so they stay in one top-level
`frontend/e2e/` rather than being awkwardly forced into either feature.

## Consequences

`ls app/catalog/` answers every question about the catalog, including what
is verified, without a second lookup into a parallel tree. The standard
objection — colocated tests ship inside the package — does not apply here:
nothing builds a wheel, systemd runs the backend from a checkout, so test
files sitting next to the code they test cost nothing at runtime.
