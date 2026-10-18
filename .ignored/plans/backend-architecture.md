# Backend architecture: layered features

## Goal

- Three layers, each a folder: `entry/` composes `features/`, features use `core/`.
- One folder per feature. Every feature folder is flat and uses the same file names.
- Features never import each other.
- `entry/mcp/` has one file per tool.
- Shared logic lives in one place (`core/`). A feature can hold a thin adapter over it.
- Deepest path: `backend/app/<layer>/<package>/<file>.py`.
- The tree below is the target. Small changes during implementation are fine.

## Layers

    entry/      api/ mcp/ cli/                     the ways in: HTTP, MCP, command line
    features/   catalog/ stories/ curation/ collect/ newsletter/ audience/ analytics/
    core/       db/                                tables + engine
                settings.py http.py extract.py ... mechanism, flat beside db/

Import rules:
- The flat `core/*.py` modules import only stdlib and third-party packages, never `core.db`.
- `core.db` imports the flat `core` modules (settings, dates).
- A feature imports `core`. It never imports another feature.
- `entry.api`, `entry.mcp`, `entry.cli` import `features` and `core`. They never import each other.
- `app/main.py` wires `entry.api` and `entry.mcp` into one FastAPI app.
- Enforced with import-linter (`lint-imports`) in pre-commit and CI:
  - a `layers` contract: `app.main` > `app.entry` > `app.features` > `app.core`
  - an `independence` contract over the `app.features.*` packages
  - an `independence` contract over `app.entry.api`, `app.entry.mcp`, `app.entry.cli`
  - a `forbidden` contract: the flat `app.core.*` modules may not import `app.core.db`

## Target tree

Every Python folder also has an `__init__.py`. Test file names are approximate: they follow the code, and some existing test files merge or split.

```
backend/
  pyproject.toml              + [tool.alembic] (alembic 1.18), replaces alembic.ini
  conftest.py
  migrations/                 was app/alembic
    env.py
    script.py.mako
    versions/                 30 existing migrations, unchanged
  app/
    main.py                   FastAPI app, routers in today's order, /mcp mount (absorbs router.py)

    entry/
      api/                    one file per router; handlers stay thin
        deps.py
        login.py
        users.py
        likes.py
        articles.py
        stories.py
        analytics.py
        test_login.py
        test_users.py
        test_likes.py
        test_articles.py
        test_analytics.py
      mcp/                    one file per tool
        server.py             FastMCP instance, instructions, tool list
        auth.py               SharedSecret, WRITE_SCOPE, require_write
        sql_query.py
        web_fetch.py
        web_search.py
        list_candidates.py
        get_content.py
        similar.py
        stories.py
        check_link.py
        vocabulary.py
        approve.py
        reject.py
        reject_many.py
        week.py
        related.py
        draft_issue.py
        story_candidates.py
        save_story.py
        close_story.py
        test_server.py
        test_sql_query.py
        test_curation_tools.py
      cli/                    run by systemd, the deploy, or by hand
        collect.py            was `python -m pipeline.run`
        report.py             was `python -m pipeline.report`
        backup_db.py
        prestart.sh
        wait_for_db.py
        create_superuser.py
        seed_tags.py
        tags.json
        seed_articles.py
        seed_stories.py
        backfill_publishers.py
        find_missing_tags.py
        test_wait_for_db.py

    features/
      catalog/                the public feed: list, search, facets, voices, stats
        model.py
        service.py
        semantic_search.py
        facets.py
      stories/                the right rail's named threads
        model.py
        service.py
        test_service.py
      curation/               the agent's verbs: candidates, coverage, approve, reject
        model.py
        service.py
        coverage.py
        publish.py
        tags.py
        links.py
        test_service.py
        test_service_db.py
        test_tags.py
        test_publish.py
        test_links.py
      collect/                was pipeline/: sources -> extract -> known-URL filter -> queue
        model.py
        service.py
        fetch.py
        filter.py
        queue.py
        hn.py
        feeds.py
        newsletters.py
        lab_watch.py
        github_stars.py
        tweets.py
        titles.py
        freshness.py
        publishers.py
        runs.py
        report.py
        test_service.py
        test_fetch.py
        test_queue.py
        test_hn.py
        test_feeds.py
        test_newsletters.py
        test_tweets.py
        test_titles.py
        test_freshness.py
        test_publishers.py
        test_publishers_db.py
        test_runs.py
        test_report.py
      newsletter/             subscribers, week/related, draft issue
        model.py
        service.py
        broadcast.py
        weekly_issue.html
        test_service.py
        test_broadcast.py
        test_subscribe.py
      audience/               users, sign-in links, likes
        model.py
        service.py
        email.py
        sign_in.html
        welcome.html
        test_service.py
      analytics/              events, admin report
        model.py
        service.py
        test_service.py

    core/
      db/                     one file per table, plus the engine
        __init__.py           imports every table module
        engine.py
        publisher.py
        article.py
        tag.py
        story.py
        ledger.py
        run.py
        user.py
        like.py
        subscriber.py
        event.py
        factories.py
        test_enums.py
        test_ledger.py
      settings.py             mechanism, flat beside db/
      logging.py
      dates.py
      security.py
      email.py
      http.py
      web_search.py
      extract.py
      github.py
      urls.py
      embedding.py
      jev.py
      llm_text.py
      test_logging.py
      test_extract.py
      test_github.py
      test_urls.py
      test_jev.py
      test_llm_text.py
      test_embedding.py
```

Removed: `pipeline/`, `backend/scripts/`, `backend/tests/`, `alembic.ini`, `app/router.py`, every `tests/` subfolder. `test.sh` and `tests-start.sh` move to root `scripts/`.

Unchanged: `backend/baml_src/` and `backend/baml_client/` stay where they are (BAML is out of scope); `features/collect/newsletters.py` keeps importing `baml_client`.

## What a feature folder holds

- `model.py`: the feature's own types: request/response shapes, TypedDicts, errors, enums that aren't stored. No tables.
- `service.py`: the verbs entry calls, as `session` plus plain arguments, returning domain types. This is the feature's interface. Entry imports a feature's `service` and `model` only.
- `<mechanism>.py`: an adapter over a `core` module, named after it. Example: `audience/email.py` builds the sign-in and welcome mails and sends them through `core/email.py`.
- Other files are private helpers named after what they hold (`facets.py`, `coverage.py`, `hn.py`). Only the feature itself imports them.
- `test_<file>.py` beside the file it tests. No `tests/` folder.
- Non-Python files sit beside their single consumer: `audience/sign_in.html`, `newsletter/weekly_issue.html`.

## core/db/

What it contains:
- The table classes (SQLModel `table=True`): Article, Publisher, Tag, Story, Reject, PipelineRun, User, ArticleLike, NewsletterSubscriber, AnalyticsEvent, and the enums stored in their columns.
- The engine and `get_session`, the one connection to Postgres.
- A few small rules on those tables that two or more features need.

What it doesn't contain: queries one feature owns, API shapes, business logic. "List the feed" is in `features/catalog/service.py`, which imports `Article` from `core.db`.

Example: today `Article` is in app/catalog/models.py, and pipeline, curation, newsletter, stories, audience and analytics all import it from catalog. That's why the domains depend on each other now. After: `from app.core.db.article import Article` everywhere, and `catalog/model.py` keeps only `ArticlePublic` and friends.

Why there:
- The table graph is shared. Six of seven features read `Article`. The foreign keys cross every boundary: like -> user + article, story_article -> article, article -> publisher, scored_url -> publisher.
- Tables in each feature's `model.py` would force sideways imports.
- Migrations are already one linear history over the whole schema.
- `db/__init__.py` imports every table module, so `SQLModel.metadata` is complete whenever `app.core.db` is imported. That removes today's trap where a new domain needs a line in `alembic/env.py` or autogenerate skips its tables.

Files:
- `engine.py`: one engine plus `get_session`. Today there are two (app/platform/db.py and pipeline/db.py).
- `publisher.py`: Publisher, PublisherKind, PublisherType, TrustLevel, LinkPlatform, slugify.
- `article.py`: Article, ArticleKind, Category, kind_from_url (was pipeline/url_kind.py; curation and newsletter both read it).
- `tag.py`: Tag, ArticleTag.
- `story.py`: Story, StoryArticle.
- `ledger.py`: Reject, RejectStage, record_reject, CONTENT_CAP, CANDIDATE_CAP. collect writes pending rows, curation writes verdicts, newsletter reads the ledger.
- `run.py`: PipelineRun.
- `user.py`: User.
- `like.py`: ArticleLike, like_counts_subquery (catalog and newsletter both read it).
- `subscriber.py`: NewsletterSubscriber.
- `event.py`: AnalyticsEvent.
- `factories.py`: test factories (was audience/tests/factories.py, catalog/tests/factories.py, tests/random_data.py).
- `test_enums.py`: was tests/test_models_enums.py.

## core/ (shared logic)

Flat modules beside `db/`. No `shared/` folder, so ADR 3 and the banned-name hook need no exception.

- `settings.py`, `logging.py`, `security.py`: from app/platform, unchanged.
- `dates.py`: get_datetime_utc, plus parse_date (from pipeline/freshness.py; the ledger and curation both use it).
- `email.py`: jinja render plus Resend/SMTP send. Absorbs pipeline/report.py's own Resend call (send_mail). Templates move to their consumers.
- `http.py`: fetch_with_timeout, BROWSER_HEADERS (from pipeline/fetching/http.py).
- `web_search.py`: tavily_search, split out of http.py.
- `extract.py`: page -> text, tables, outbound links (from fetching/extract_content.py plus outbound_links from fetching/page_facts.py).
- `github.py`: URL parsing (from pipeline/github.py) plus the API calls repo_for, has_readme, account_type (from sources/github_stars.py).
- `urls.py`: hostname, feed_url (from pipeline/urls.py), is_first_party (from pipeline/first_party.py).
- `embedding.py`: model, embed_batch, embedding text, SNIPPET_CAP, cosine_distances, nearest, story_groups (from pipeline/embedding.py, steps/__init__.py, and the maths in pipeline/curation.py).
- `jev.py`: from pipeline/jev.py, unchanged.
- `llm_text.py`: from pipeline/llm_text.py, unchanged. `enum_value` is read by collect and curation, so it stays shared while BAML stays.

## Sideways imports today and where each goes

| today | after |
|---|---|
| everything -> catalog.models / audience.models / pipeline.models (tables) | `core/db/` |
| audience/routes -> catalog.articles.list_liked_articles, newsletter.subscribers.subscribe | `entry/api/users.py` and `entry/api/login.py` compose the three features |
| catalog/stories -> pipeline.curation cosine_distances, story_groups | `core/embedding.py` |
| newsletter/digest -> curation maths, embedding, SNIPPET_CAP, Reject, url_kind, like_counts_subquery | `core/embedding.py`, `core/db/ledger.py`, `core/db/article.py`, `core/db/like.py` |
| mcp/tools -> pipeline.fetching extract, page_facts, tavily | web_fetch/web_search -> core; check_link facts -> `features/curation/links.py` |
| pipeline/curation -> steps.persist, steps.enrich, tags | inside `features/curation/` (approve is the only article writer, ADR 9) |
| page_facts, publishers -> sources.github_stars API helpers | `core/github.py` |
| scripts/backfill_publishers -> curation.NAMEABLE_KINDS, publishers | `entry/cli/` (may import any feature) |

## File moves

All feature paths below are under `app/features/`.

catalog/
- `model.py`: ArticlePublic, ArticlesPublic, PublisherPublic, TagPublic, facets, OriginCounts, Voice, Origin (from catalog/models.py).
- `service.py`: was catalog/articles.py.
- `semantic_search.py`, `facets.py`: stay (ADR 2 names).

stories/
- `model.py`: StoryPublic, StoryArticlePublic, plus the TypedDicts in catalog/stories.py.
- `service.py`: was catalog/stories.py.

curation/
- `model.py`: CandidatePage, ContentPage, Neighbour, Similar, Verdict, CandidateError, Coverage (was `Story`, renamed so it isn't mistaken for the stories feature), and Scored/Summarized/Persisted/ProcessedArticle from pipeline/types.py.
- `service.py`: list_candidates, get_content, similar, stories, vocabulary, approve, reject, reject_many (from pipeline/curation.py).
- `coverage.py`: feed/ledger row loading behind similar and stories.
- `publish.py`: insert_articles, best_per_url, embed_articles (was steps/persist.py, steps/enrich.py).
- `tags.py`: was pipeline/tags.py.
- `links.py`: check_link facts (repo/model lookup half of fetching/page_facts.py).

collect/
- `model.py`: RawItem, Candidate (pipeline/types.py), RunStats, SourceStats.
- `service.py`: run() (body of pipeline/run.py).
- `fetch.py`, `filter.py`, `queue.py`: were steps/.
- `hn.py`, `lab_watch.py`, `github_stars.py`: were sources/.
- `feeds.py`: was sources/substack.py. It fetches every rss and substack feed.
- `newsletters.py`: was sources/email.py. Renamed so it isn't confused with core/email.py.
- `tweets.py`: was fetching/tweets.py.
- `titles.py`, `publishers.py`, `runs.py`: names unchanged.
- `freshness.py`: is_within_window only.
- `report.py`: read_night, format_night, subject. Sending goes through core/email.

newsletter/
- `service.py`: week, related (was digest.py), plus subscribe (was subscribers.py, 30 lines).
- `broadcast.py`: post rules, render, Resend broadcast. Stays.
- `weekly_issue.html`: from platform/email-templates.

audience/
- `model.py`: UserCreate, UserUpdateMe, UserPublic, Token, TokenPayload, SignInRequest, MagicLogin, Message.
- `service.py`: stays.
- `email.py`: sign-in and welcome mails (from platform/email.py).
- `sign_in.html`, `welcome.html`: from platform/email-templates.

analytics/
- `model.py`: report shapes and AnalyticsEventCreate.
- `service.py`: was report.py.

entry/
- catalog/routes.py -> api/articles.py + api/stories.py.
- audience/routes.py -> api/login.py, api/users.py, api/likes.py.
- analytics/routes.py -> api/analytics.py.
- app/deps.py -> api/deps.py.
- app/router.py -> folded into app/main.py.
- app/mcp/tools.py -> one file per tool in mcp/. A tool file is an adapter: parse arguments, call one feature verb, shape the result. sql_query keeps its read-only/blocked-table logic in its own file, because nothing else uses it.
- backend/scripts/*.py and prestart.sh -> cli/.

Tests: tests/pipeline/*, tests/platform/*, tests/scripts/*, app/*/tests/* -> `test_<file>.py` beside the moved module.

## Out of scope

- BAML removal. `baml_src/` and `baml_client/` stay at `backend/`, their pyproject/pre-commit/typos excludes stay, and the CLAUDE.md regen rule stays. Notes for a later change: only SelectNotableItems and SelectProductLink are still called (both in the newsletter source), ClassifyProfiles has no caller, and NVIDIA_NIM_*/MISTRAL_AI_* are in neither .env.dev nor deploy/README.

## Deploy

- Today the deploy rsyncs the whole checkout to /opt/agentique, except .git, .env, .venv and frontend dist.
- What the box needs:
  - `backend/app/` without test_*.py
  - `backend/migrations/`
  - `backend/pyproject.toml`
  - `backend/baml_client/`
  - root `pyproject.toml`, `uv.lock`, `.python-version` (for `uv sync --package app`)
  - `compose.yml` (the backup unit runs `docker compose exec`, which finds it by walking up from backend/)
  - `deploy/agentique-sql`
  - `frontend/dist`
- Last step: rsync with an include list and `--exclude 'test_*.py'`.
- New ExecStart lines: `-m app.entry.cli.collect`, `-m app.entry.cli.report`, `app/entry/cli/backup_db.py`. `fastapi run ... app/main.py` is unchanged.
- The systemd units are installed by hand. Copy them and run `daemon-reload` right after the deploy that changes ExecStart, before 03:30 (backup) and 04:00 (pipeline). Otherwise that night's timers fail with ModuleNotFoundError. Or have the deploy job install them, if the runner's sudoers allows it.

## What stays fixed

- OpenAPI: same tags, handler function names and router order. The generated client comes out byte-identical (`scripts/generate-client.sh`, then an empty diff in frontend/src/client).
- MCP: same tool names, docstrings and parameters. The three routines and the curate regression set depend on them. Diff a `tools/list` dump before and after.
- Schema: `alembic check` reports no diff after the tables move.
- The `app` package name and `app.main:app`.
- The MCP tool `stories` (curation coverage) keeps its name even though a `stories/` feature exists. Renaming it would change the curate rubric's tools.

## Costs and risks

- `mypy --strict` runs over app/ and scripts/ today. Once pipeline code is under app/ it gets checked too: `mypy pipeline` reports 60 errors in 13 files now, mostly explicit `Any`. Fix them file by file during the move, no per-module ignores.
- ADR 7: with one engine in core/db, the collect run builds Settings for the database URL. The box already feeds both processes the same .env. Per-source knobs keep reading os.environ beside their consumer.
- ADR 8: the stage-type chain splits at the queue. collect owns RawItem -> Candidate. curation builds Scored -> Persisted from the ledger row, without subclassing collect's types.
- Config: testpaths = ["app"], coverage source = ["app"], omit `*/test_*.py`, `*/conftest.py`, `*/factories.py`. T201 per-file ignore moves to `app/features/collect/**` and `app/entry/cli/**`. mypy/ty entries cover `backend/app` only.
- About 130 files move. Every step below leaves the suite green and is its own commit.

## Order of work

1. `core/`: app/platform moves to app/core. Pipeline mechanism moves in (http, web_search, extract, github, urls, embedding, dates, jev, email send).
2. `core/db/`: tables move, the two engines merge, migrations to backend/migrations, alembic config into pyproject. Check: `alembic check` clean.
3. `features/`: catalog, audience, newsletter, analytics move; `stories/` splits out of catalog; `curation/` and `collect/` come out of pipeline. Fix mypy as files enter the checked tree.
4. `entry/`: `api/` from routes, `mcp/` one file per tool, `cli/` from scripts + pipeline entrypoints. Check: client diff empty, `tools/list` diff empty.
5. Flatten tests, factories to core/db, pytest/coverage config.
6. import-linter contracts in pyproject, pre-commit and the test-backend workflow.
7. Deploy: include-list rsync, new ExecStart lines, reinstall units on the box.
8. Docs: new ADR "layered features" superseding 1 and 4 (ADRs aren't edited), style.md, docs/backend.md, glossary paths, deploy/README env table paths, CLAUDE.md (MCP path).

## Decided

- Layers: `entry/` / `features/` / `core/`.
- Features never import each other.
- Tables in `core/db/`.
- Shared mechanism flat in `core/`, beside `db/`.
- BAML removal out of scope.
- Routes in `entry/api/`.
- pipeline/ becomes `features/collect/`.

## Open

- Nothing blocking. Small tree adjustments are fine during implementation.
