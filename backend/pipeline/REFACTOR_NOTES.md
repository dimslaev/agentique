# Pipeline refactor — new schema (Publisher / normalized Article / Tags)

Kickoff refactor of `backend/pipeline/**` onto the redesigned data model in
repo-root `models.py`. Scope was `backend/pipeline/` + new BAML. Python is **not
expected to import/compile** — no DB, no `baml_client`, no `model2vec` here.
Syntax checks pass (`python -m py_compile`).

## What changed

### New schema, importable by the pipeline
- `app/models_agentique.py` — ported repo-root `models.py`:
  - New enums: `PublisherKind`, `TrustLevel`, `ArticleKind`, `Category`,
    `Channel`, `LinkPlatform`.
  - New tables: `Publisher`, `Tag`, `ArticleTag`. `Article` **replaced** —
    `publisher_id` FK (was `source`), `channel` enum (was `source_type`), `kind`
    is `ArticleKind`, `categories` is `list[Category]`.
  - `ArticleLike` re-added with tz-aware `created_at`.
  - New `slugify(name) -> str` helper (ASCII-fold, lowercase, non-alnum→hyphen).
  - Kept pipeline-support tables untouched: `ScoredUrl`, `PipelineRun`,
    `AnalyticsEvent`(+`Create`), `NewsletterSubscriber`(+req/resp).

### Publisher concept + DB-driven ingestion (new file)
- `pipeline/publishers.py` — new:
  - `PublisherResolver` — resolves a fetched item's source name → `Publisher`
    row (by `slugify`), caching slug→row per run. Unknown source →
    auto-**quarantined** publisher (`is_active=False`, `kind=media`,
    `trust=medium`); logs + counts them.
  - `feed_sources_from_db(session)` — active publishers with an rss/substack
    link → `[{name, rssUrl}]`. Replaces `substack-sources.json` at runtime.
  - `channel_for(source_type)` / `CHANNEL_BY_SOURCE_TYPE` — deterministic
    `source_type` → `Channel` (`hackerNews→hackernews`, `aiNews→ainews`,
    `newsletter→newsletter`, `rss→rss`). **Not** an LLM call.

### run.py wiring
- `SOURCES` constant → `_build_sources(session)`. HN / AI News / Newsletter keep
  their fetchers; substack is now the single **"Feeds"** source driven by
  `feed_sources_from_db`.
- New `_resolve_publishers(...)` step (right after fetch) stamps each item with
  `publisher_id` and `trust` (from `Publisher.trust`). **`channel` is treated as
  provenance/observability, not consumer data**: it's derived from `source_type`
  via `channel_for()` at the single point of use (article insert), so the derived
  value doesn't flow through the pipeline as a loose dict key. Per-run,
  per-channel counts already live in `PipelineRun.sources` (fetcher label maps
  1:1 to channel), so the observability doesn't depend on `Article.channel`.
- `_to_baml_input` — `trust` now from the stamped item (was `TRUST_BY_SOURCE`).
- `_dedup_semantic` — `ExistingArticle.source` now filled from a
  `publisher_id → name` lookup (Article no longer has `source`).
- `_insert_articles` — builds `Article(publisher_id=…, channel=…)`.
- `_summarize_and_categorize` — maps BAML enums → `Category` / `ArticleKind`
  via new `_to_categories` / `_to_kind` helpers (drops off-enum values).
- New `_assign_tags(...)` step (Step 08b) after categorize — see below.

### steps.py
- `kind_from_url` now returns `ArticleKind | None` (was lowercased str).
- `TRUST_BY_SOURCE` **deleted** — trust comes from `Publisher.trust`.

### Tag assignment (the main new LLM work)
- `baml_src/tags.baml` — new: `TagSlug` enum (all 29 slugs, underscore member
  names + `@alias` = canonical slug + `@description`), `TagInput`,
  `TagAssignment`, and `AssignTags(articles) -> TagAssignment[]` (batched,
  id-keyed).
- `pipeline/tags.py` — new: `TAG_NAMES`/`TAG_SLUGS` vocabulary, `validate_tags`
  (normalize → drop off-list → dedupe → cap 3), `get_or_create_tag`,
  `write_article_tags`. Post-validation guarantees only vocabulary slugs land in
  the DB even if the model drifts.

### substack.py
- Extracted `fetch_feeds(sources)` (parallel feed fetch given DB-supplied
  sources). `fetch_substack()` kept as a **deprecated seed-only** path that
  reads the JSON; no longer wired into the run.

## TODO(new-schema) breadcrumbs left in code
- `app/models_agentique.py:133` — `ArticlePublic`/`ArticlesPublic` still extend
  the new `ArticleBase` but the read API isn't reworked (see out-of-scope).
- `pipeline/run.py:320` — hard-coded "Ben's Bites" +10 score bonus; should move
  to a Publisher boost/weight field.
- `pipeline/health.py:47` — `SourceStats.source` is the fetcher label (≈Channel
  now), not a publisher. Fine as a stats key; revisit if per-publisher health is
  wanted. `PROBE_URL_BY_SOURCE` still keyed by aggregator labels.

## Out-of-scope follow-ups (NOT done — need separate work)
- **`substack-sources.json`** (`pipeline/sources/substack-sources.json`) — keep
  as a one-time **seed** for the `Publisher` table (name + rss/substack link →
  publisher rows), then it can be retired. No seeding script written.
- **models_agentique reconciliation** — decide whether repo-root `models.py`
  stays the source of truth or is deleted now that it's ported. If ported copy
  is canonical, remove/redirect `models.py`.
- **Read API** — `app/api/routes/articles.py`, `likes.py`, and
  `ArticlePublic`/`ArticlesPublic` shape: expose `publisher`/`kind`/`categories`/
  `tags`, join `Publisher` for the source name, add tag filtering. **Omit
  `channel` from `ArticlePublic`** — it's pipeline provenance, not consumer data
  (kept as a column to match models.py + the migrated prod DB, but not exposed).
  Decision: keep the `Article.channel` column rather than drop it; dropping would
  diverge from the source-of-truth schema and need a prod migration for no
  consumer benefit.
- **Frontend client** — `frontend/src/**` + generated `types.gen.ts` /
  `sdk.gen.ts` / `schemas.gen.ts` regen after the API schema settles.
- **Alembic** — new migration for `publisher`, `tag`, `article_tag`, the
  `article` reshape (`publisher_id`/`channel`/enum columns), and FK/backfill.
  Prod DB was already migrated by a one-shot script; a matching alembic revision
  still needs authoring (`app/alembic/versions/`).
- **Tests** — `backend/tests/**` referencing old `Article(source=…,
  source_type=…)` and article routes need updating; add coverage for
  `slugify`, `PublisherResolver` quarantine, `validate_tags`, `channel_for`.
- **BAML client generation** — `AssignTags` + `TagSlug`/`TagInput`/
  `TagAssignment` need `baml_client` regen before `run.py` imports resolve.
- **`email.py` / `rss.py` sources** — still stamp `source_type` strings (handled
  by `channel_for`); their per-item `source` names must exist as publishers or
  they'll be quarantined. Seed those publishers when seeding feeds.
