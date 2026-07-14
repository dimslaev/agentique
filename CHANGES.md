# Changes on top of `fastapi/full-stack-fastapi-template`

---

## 2026-07-14 — mirror pgvector image to GHCR

- New file: `.github/workflows/mirror-pgvector.yml` — pulls `pgvector/pgvector:pg17` from Docker Hub and pushes it to `ghcr.io/dimslaev/pgvector:pg17`. Manual (`workflow_dispatch`) + monthly schedule to pick up upstream security patches. Prompted by the prod deploy's self-hosted runner hitting Docker Hub's anonymous pull rate limit (`429`) on `docker compose pull`.
- `compose.yml` — upstream file. `db.image` `pgvector/pgvector:pg17` → `ghcr.io/dimslaev/pgvector:pg17`. Low conflict risk.

## 2026-07-13 — SEO audit fixes: SPA meta, robots.txt, blog soft-404

- `frontend/index.html` — upstream file. Replaced the template's default `Full Stack FastAPI Project` title (no meta description, broken `/vite.svg` favicon reference) with real title/description/canonical/OG tags for the root domain; dropped the dead favicon link. Low conflict risk.
- New file: `frontend/public/robots.txt` — bare `Allow: /`. No `Sitemap:` line yet (sitemap.xml isn't generated — deferred, see `plans/blog-ssg-cron.md`).
- `frontend/nginx.conf` — upstream file. New `location /blog` block (`try_files $uri $uri/ =404`) so unknown post slugs 404 for real instead of falling through to the SPA shell with `200` (a soft-404). Verified against a local nginx container: `/blog`→301→`/blog/`, real posts 200, unknown slugs 404, SPA client routes (`/profile`, unknown app paths) still 200 via the unchanged `location /` fallback. Low conflict risk.
- `frontend/scripts/prerender-blog.ts` — `MAX_TITLE_CHARS` 70 → 55: the rendered `<title>` appends `· agentique` (12 chars), so the old cap let the total tag exceed Google's ~60-70 char display budget.
- `.agents/blog-writer.md` — title contract comment updated to match the new 55-char cap.
- `frontend/content/blog/2026-07-13-whats-new-with-ai-agents.md` — shortened title to fit the new cap.

## 2026-07-12 — sanitize + validate LLM titles and summaries

- `backend/pipeline/utils.py` — `sanitize_llm_text()` now also strips markdown emphasis. New `is_corrupted()` (non-Latin script / leaked JSON envelope), `is_valid_title()`, `is_valid_summary()`. `strip_title_wrappers()` peels nested wrappers to a fixed point.
- `backend/pipeline/run.py` — `_improve_titles()` keeps the original title when a rewrite fails validation; `_summarize()` drops a summary that fails validation rather than storing garbage.
- `baml_src/fix_titles.baml`, `baml_src/summarize.baml` — prompts forbid markdown / non-English / JSON / truncation. Added `@@assert` regression tests built from real corrupted prod rows.
- `backend/app/api/routes/articles.py` — `col(Article.score)` / `col(Article.kind)` in the filter conditions; drops stale `type: ignore[operator]` + `ty: ignore[unsupported-operator]` that no longer matched what mypy/ty emit.
- `backend/app/api/article_view.py` — `assert article.id is not None` / `assert publisher.id is not None` instead of `type: ignore[arg-type]`.
- `backend/app/seed_tags.py` — build `Tag(slug=, name=, description=)` explicitly instead of `Tag(**entry)` (ty widened the dict values to `str`).
- `backend/pyproject.toml` — upstream file. Ruff `exclude` gains `baml_client` (generated). Low conflict risk.
- `pyproject.toml` — upstream file. Typos `extend-exclude` gains `backend/baml_client/`. Low conflict risk.
- `.pre-commit-config.yaml` — upstream file. `end-of-file-fixer` and `trailing-whitespace` exclude `backend/baml_client/`. Low conflict risk.

## 2026-07-10 — email a pipeline report every run, not just on anomalies

- `backend/pipeline/health.py` — `verify_run()` now always emails via `_send_alert()` (subject varies: "anomalies detected" vs "Pipeline run report"); `_format_report()` shows a "No anomalies detected." line instead of omitting the email entirely.

## 2026-07-10 — fully DB-driven ingestion sources, remove dead code

- `backend/app/models_agentique.py` — `LinkPlatform` gains `email`, for publishers only reachable via the IMAP newsletter source (no public RSS feed).
- `backend/pipeline/publishers.py` — new `newsletter_senders_from_db()`, mirrors `feed_sources_from_db()`: active publishers with an `email` link -> `(sender pattern, name)`.
- `backend/pipeline/sources/email.py` — removed the hardcoded `NEWSLETTER_SOURCES` list; `_match_sender`/`_run_imap_fetch`/`fetch_newsletter` now take `sources` as a parameter.
- `backend/pipeline/run.py` — `Newsletter` source now built the same way as `Feeds`: `fetch_newsletter(newsletter_senders_from_db(session))`.
- Deleted dead code: `backend/pipeline/sources/rss.py` (had correct feed URLs for several sources but was never imported by `run.py`), `backend/pipeline/sources/substack-sources.json` and `substack.py::fetch_substack()` (superseded by DB-driven `feed_sources_from_db`, already marked DEPRECATED), `backend/pipeline/sources/utils.py::is_twitter_url()`/`resolve_twitter_url()` (only caller was `rss.py`).
- Prod DB: audited all active publishers for a missing feed link (same bug class as Ben's Bites/TLDR/AI Hero). Added `rss` links to 24 publishers with a confirmed working feed (incl. reviving the ones stranded in dead `rss.py`: Console, Aligned News, The Neuron, Import AI; plus company blogs — HF, OpenAI, DeepMind, TechCrunch — and ~15 individual Substack/Ghost newsletters). Added `email` links (moved off the Python hardcode) to the 7 publishers with no public feed: The Frontier by Product Hunt, The Batch, Pointer, There's An AI For That, The Rundown AI Tech, Superhuman, AgentAI. Created 3 new publisher rows for previously-untracked sources: The Neuron, Import AI, Changelog News (moved off IMAP). `ThursdAI` has neither a working feed nor a known sender address — still unresolved.

## 2026-07-10 — fix dead pipeline feed sources

- `backend/pipeline/publishers.py` — `feed_sources_from_db()` was polling `publisher.links["substack"]` as-is; those are stored as the base site URL (e.g. `https://foo.substack.com`), not the feed endpoint, so every DB-driven feed returned 0 entries. Added `_feed_url()` to append `/feed` for `substack` links.
- `compose.yml` — upstream file. Added `IMAP_HOST`/`IMAP_PORT`/`IMAP_USER`/`IMAP_PASSWORD` and `TAVILY_API_KEY` to the `pipeline` service `environment:` allowlist — these secrets existed in GitHub but were never forwarded into the container. Low conflict risk.
- `.github/workflows/deploy-production.yml` — upstream file. Added the same `secrets.IMAP_*` / `secrets.TAVILY_API_KEY` to the `deploy` job `env:` block so compose can interpolate them. Low conflict risk.

## 2026-07-09 — normalized article schema (publisher + tags)

- `backend/app/alembic/versions/b2c3d4e5f6a7_add_publisher_model.py` — new head (`down_revision = a7b8c9d0e1f2`). **Destructive**: drops `article_like` + `article`, creates `publisher`/`tag`/`article_tag` and the new `article` (`publisher_id` FK, `articlekind`/`publisherkind`/`trustlevel` PG enums), recreates `article_like` and the three article indexes. Not an upgrade path for prod — prod gets the prepared dump + `alembic stamp head`.
- `backend/app/seed_articles.py` — rewritten for the new schema (sample publishers, `publisher_id`, enum `kind`, tag links). No longer wipes `article`/`publisher`: it returns early when `article` is non-empty, so a DB loaded from the real dump survives `prestart`.
- `backend/scripts/prestart.sh` — one added line: `python -m app.seed_tags` before `seed_articles`. Runs in **all** environments; `pipeline.tags.load_vocabulary()` raises on an empty `tag` table. Low conflict risk.
- New files: `backend/app/seed_tags.py` (idempotent upsert keyed on `slug`), `backend/app/data/tags.json` (29-tag controlled vocabulary), `backend/app/api/article_view.py` (shared read-side shaping for articles/likes).
- `backend/tests/utils/article.py` — `create_random_article` now creates a `Publisher`; added `create_random_publisher` / `create_random_tag` / `tag_article`.
- `backend/app/models_agentique.py` — enums `(str, Enum)` → `StrEnum` (ruff `UP042`). Same member names, so the PG enum labels are unchanged.
- `backend/app/api/deps.py` — `ruff format` only: `except (A, B):` → `except A, B:` (PEP 758, valid on the pinned Python 3.14). Cosmetic, but it is an upstream file — expect a trivial conflict on merge.
- `frontend/src/components/Articles/ArticleRow.tsx` — `article.source` → `article.publisher.name`; renders `article.tags`.
- `frontend/src/routes/_layout/developers.tsx` — API docs: response shape gains `publisher`/`tags`/`like_count`/`liked_by_me`, drops `source`/`source_type`; documents the `tag` filter and `likes-desc` sort.

## 2026-07-07 — newsletter + RSS pipeline sources

- `backend/pyproject.toml` — `imap-tools` dependency.
- New files: `backend/pipeline/sources/email.py` (IMAP newsletter source, wired into `SOURCES`), `backend/pipeline/sources/rss.py` (generic multi-feed RSS source, not wired in — mirrors original TS, which also had it disabled).

## 2026-07-06 — first-party analytics tracker

- `backend/app/models_agentique.py` — new `AnalyticsEvent` table (`analytics_event`, nullable `user_id` FK, JSON `props`, indexed event/path/visitor_id/created_at) + `AnalyticsEventCreate` request model.
- `backend/app/api/routes/analytics.py` — new: `POST /analytics/collect`, public, `CurrentUserOptional` attaches user when authed, returns 204. Truncates strings to 2048.
- `backend/app/alembic/versions/a7b8c9d0e1f2_add_analytics_event_table.py` — new migration (head → a7b8c9d0e1f2).
- `backend/app/api/main.py` — upstream. Mounts `analytics.router`. Low conflict risk.
- `backend/tests/conftest.py` — upstream. Teardown deletes `analytics_event` before users (non-cascading `user_id` FK). Low conflict risk.
- `backend/tests/api/routes/test_analytics.py` — new: anonymous/authed collect, default event, custom props, truncation.
- `frontend/src/lib/analytics.ts` — new: `trackPageview`/`trackEvent` POST to backend via `fetch` (keepalive), persists anon `visitor_id` in localStorage, works logged-out, swallows errors. No generated-client change (plain fetch).
- `frontend/src/main.tsx` — upstream. `router.subscribe("onResolved", ...)` fires a pageview per SPA navigation. Low conflict risk.

---

## 2026-07-06 — pipeline health check

- `backend/pipeline/health.py` — new: per-run stats capture, dead-man's-switch, arithmetic anomaly detection (fetched-0/yield-drop/errors), HTTP probe, Resend alert. Reads config from `os.environ` (not `settings`) to stay decoupled.
- `backend/pipeline/run.py` — `run_pipeline()` now takes a `RunStats`, wraps each source in try/except (one source failing no longer sinks the rest), and `__main__` runs liveness → pipeline → record → verify. Agentique-owned file.
- `backend/app/models_agentique.py` — new `PipelineRun` table (JSONB `sources` funnel counts).
- `backend/app/alembic/versions/f1a2b3c4d5e6_add_pipeline_run_table.py` — new migration (head → f1a2b3c4d5e6).
- `compose.yml` — `pipeline` service env: added `PROJECT_NAME`, `RESEND_API_KEY`, `EMAILS_FROM_EMAIL`, `PIPELINE_ALERT_EMAIL` (verifier email needs them; `.env` is empty on the VPS so vars must be in the `environment:` block). Low conflict risk.
- `.github/workflows/deploy-production.yml` — added optional `PIPELINE_ALERT_EMAIL` env (falls back to `EMAILS_FROM_EMAIL`). Low conflict risk.

## 2026-07-05

- `frontend/src/main.tsx` — `currentUser` query `onError` clears token and redirects to `/login` on `400/401/403/404`; sets `retry=false` for immediate redirect.
- `frontend/tests/login.spec.ts` — mocks `/users/me` → 404, asserts token clearing + redirect.
- `backend/app/api/routes/login.py` — in dev, logs reset link to console instead of asserting `emails_enabled` (fails locally).

## 2026-07-04 — merge upstream/master (10 commits)

Merged `fastapi/full-stack-fastapi-template@a758585` (release-notes + dep bumps only).

- `uv.lock` — re-locked from ours in a `uv:python3.14-bookworm-slim` container. Minimal bump: `emails` 0.6 → 1.1.2.
- `backend/app/utils.py`, `backend/pyproject.toml` — took upstream `emails` 1.1.2 API change, layered on our Resend early-return.
- Workflows — `actions/checkout` v6.0.3 → v7.0.0.

## 2026-07-02

- `frontend/src/components/Common/Footer.tsx` — hand-rolled `fetch` to `/articles/stats` was missing `/api/v1` prefix, 404ing silently. Fixed.
- `backend/app/core/config.py` — `RESEND_API_KEY: str | None`; `emails_enabled` now `bool(EMAILS_FROM_EMAIL and (RESEND_API_KEY or SMTP_HOST))`.
- `backend/app/utils.py` — `send_email` uses `resend.Emails.send(...)` when `RESEND_API_KEY` set, falls back to SMTP.
- `backend/tests/api/routes/test_login.py` — `test_recovery_password` configures `RESEND_API_KEY`, asserts `resend.Emails.send`; added `test_recovery_password_smtp_fallback`.
- `backend/app/api/routes/likes.py`, `backend/app/api/deps_agentique.py`, `backend/app/alembic/versions/d4e5f6a7b8c9_add_article_like_table.py`, `backend/tests/api/routes/test_likes.py`, `backend/tests/utils/article.py` — new files: article likes (PUT/DELETE/GET auth-required, idempotent composite PK), `CurrentUserOptional` (returns `None` on any auth failure), alembic migration.
- `frontend/src/components/Articles/LikeButton.tsx`, `ArticleRow.tsx` — new: optimistic TanStack Query like toggle with cache patching, article row extracted.
- `frontend/src/routes/_layout/profile.tsx` — new: tabs Liked (default) / My profile / Password / Danger zone.
- `backend/app/models_agentique.py` — `ArticleLike` table; `ArticlePublic` gains `like_count`, `liked_by_me`.
- `backend/app/api/routes/articles.py` — LEFT JOIN `article_like` aggregate for `like_count`; per-user liked-id for `liked_by_me`; `sort=likes-desc`. Counts at query time, not denormalized.
- `frontend/src/components/Articles/ArticlesList.tsx` — renders `ArticleRow`; `data-testid`s added.
- `frontend/src/components/Sidebar/Filters.tsx` — "Popular" (`likes-desc`) sort option.
- `backend/app/api/main.py` — mounts `likes.router`.
- `backend/tests/conftest.py` — `db` teardown deletes `article_like` before users.
- `frontend/src/routes/_layout/settings.tsx` — `beforeLoad` redirect to `/profile`.
- `frontend/src/routes/login.tsx` — `redirect` search param via `Route.useSearch()`.
- `frontend/src/hooks/useAuth.ts` — `loginMutation` accepts optional `redirectTo`.
- `frontend/src/components/Sidebar/User.tsx` — "Log in" when logged out; "Profile" menu item → `/profile`.
- `frontend/src/routeTree.gen.ts`, `frontend/src/client/{schemas,sdk,types}.gen.ts` — regenerated.
- `frontend/tests/user-settings.spec.ts` — `/settings` → `/profile`; removed `test.skip`.
- `frontend/tests/login.spec.ts`, `frontend/tests/sign-up.spec.ts` — removed `test.skip`.
- `frontend/tests/utils/user.ts` — post-login assertion to sidebar user-menu visibility.
- `frontend/tests/likes.spec.ts` — new: fire button, anonymous→login redirect, optimistic toggle, sort, Liked tab; serialized.
- `backend/pyproject.toml` — dropped `login.py`, `users.py` from coverage omit; 92% coverage.
- `backend/tests/api/routes/test_login.py`, `test_users.py` — removed module-level skip; `test_recovery_password` patches `EMAILS_FROM_EMAIL`.
- `backend/app/models_agentique.py`, `backend/app/api/routes/articles.py` — `# type: ignore[import-untyped]` on `pgvector.sqlalchemy`; reordered imports for `ruff check`.
- `backend/app/api/routes/articles.py` — `# ty: ignore[...]` on `Article.score`/`Article.embedding` query lines (known `ty` false positive).
- `backend/app/seed_articles.py` — `session.execute(delete(Article))` → `session.exec(...)` (`ty` deprecation).
- `frontend/src/client/{schemas,sdk,types}.gen.ts` — regenerated; was stale, missing `private` router types.

## 2026-07-01

- `.github/workflows/test-backend.yml`, `playwright.yml`, `pre-commit.yml` — added "Create .env for CI" step (fixed non-secret values).
- `.github/workflows/deploy-production.yml` — moved `packages: write` to `build` job only (`zizmor`).
- `backend/app/api/main.py` — `"local"` → `"development"` for `private` router mount (missed in 2026-06-29 rename).
- `backend/app/api/routes/articles.py` — removed unused `sqlalchemy.or_` import. `# pragma: no cover` on `get_model()`/`_embed()` (monkeypatched in tests).
- `backend/app/seed_articles.py` — 50 deterministic sample articles, every filter dimension, 256-dim embeddings. Idempotent wipe-and-reinsert; refuses production.
- `backend/scripts/prestart.sh` — guarded `python -m app.seed_articles` after `initial_data.py`.
- `backend/pyproject.toml` — `[tool.coverage.report] omit` for upstream modules unused by Agentique; `--fail-under=90` measures only exercised code.
- `backend/tests/api/routes/test_newsletter.py` — `monkeypatch.setenv("RESEND_API_KEY"`/`"RESEND_AUDIENCE_ID")` so `resend.Contacts.create` branch is reached.
- `backend/tests/api/routes/test_articles.py` — `since=<malformed date>` fallback test.
- `frontend/src/components/Newsletter/SubscribeForm.tsx` — `noValidate` on `<form>` (browser HTML5 validation intercepted submit before React/zod).
- `tests/api/routes/test_login.py`, `test_users.py`, `test_items.py`, `test_private.py`, `tests/crud/test_user.py` — module-level skip (files kept).
- `frontend/tests/{login,sign-up,reset-password,admin,user-settings,items}.spec.ts` — file-level skip.
- New files: `backend/tests/api/routes/test_articles.py`, `test_newsletter.py` (monkeypatches `resend.Contacts.create`), `frontend/tests/newsletter.spec.ts`, `frontend/tests/articles.spec.ts`.

## 2026-06-30

- `compose.yml` — `www-http`/`www-https` Traefik routers + `redirectregex` to 301 `www.${DOMAIN}` → bare domain.
- `compose.yml` — `SHELL=/bin/sh` for pipeline (was inheriting host `zsh`, crashing).
- `compose.yml` — pipeline command `supercronic -no-reap` (PID 1 reaper crash without it).
- `backend/pipeline/crontab` — `python` → `/app/.venv/bin/python`.
- `backend/app/main.py` — `newsletter.router` mounted on `app` under `/api`.
- `backend/pyproject.toml` — `resend` dependency.
- `compose.yml` — `RESEND_API_KEY`/`RESEND_AUDIENCE_ID` for `prestart` and `backend`.

## 2026-06-29

- `backend/app/core/config.py` — `ENVIRONMENT` Literal `"local"` → `"development"`; matching guard updated.

## 2026-06-28

- `frontend/src/routes/_layout.tsx` — `beforeLoad` auth guard commented out.
- `frontend/src/routes/_layout/index.tsx` — Dashboard → `ArticlesList`.
- `.env` — deleted and gitignored.
- `compose.yml` — frontend Traefik rule `dashboard.${DOMAIN}` → `${DOMAIN}` (root domain). Added `PROJECT_NAME` to `prestart`/`backend` env.
- `.github/workflows/deploy-production.yml` — split into build (GitHub runner, pushes to ghcr.io) and deploy (self-hosted runner, pulls/restarts). Added buildx + GHA layer caching. Added missing compose env vars.
- GitHub secrets — `DOCKER_IMAGE_*` → ghcr.io URLs; `BACKEND_CORS_ORIGINS`/`FRONTEND_HOST` → `https://next.agentique.ch`; added `STACK_NAME_PRODUCTION=agentique-next`.
- `.github/workflows/deploy-staging.yml` — reverted to upstream, disabled (`workflow_dispatch` only).
- `.github/workflows/deploy-production.yml` — trigger `release: published` → `push: [master]`; added `touch .env`; added missing compose env vars.
- Neutered upstream CI `on:` triggers to `workflow_dispatch` (manual-only): `add-to-project`, `smokeshow`, `labeler`, `detect-conflicts`, `guard-dependencies`, `issue-manager`, `latest-changes`, `test-docker-compose`.

## 2026-06-27 — pipeline migration

- `backend/pyproject.toml` — `baml-py`, `trafilatura`, `feedparser`, `dnspython`, `regex`.
- `backend/Dockerfile` — supercronic install; COPY `baml_client` + `pipeline`.
- `compose.yml` — `pipeline` service (supercronic, daily 04:00).

## 2026-06-27

- `compose.yml` — db image `postgres:18` → `pgvector/pgvector:pg17`.
- `backend/pyproject.toml` — `pgvector`, `model2vec`.
- `backend/app/api/main.py` — `articles` router (items router kept).
