# Topic boxes on landing page

Replace hardcoded `SourceBoxes` (frontend/src/components/Home/sources.ts,
static JSON, no db) with live db-backed topic boxes. Each box = curated
topic, its own react-query, pulled from real article data.

## Decisions (from user)

- Lives on landing page, replaces `SourceBoxes` section in `LandingPage.tsx`
- Goal: retention (get visitor to come back / subscribe), not raw SEO
- Boxes built from structured joins (tag / category / kind / publisher /
  keyword), NOT the `/articles/search` embedding endpoint — that uses
  `model2vec potion-base-8M`, too weak for box curation. Semantic search
  capped at 0-1 optional future box, not the default mechanism
- 7 boxes, matching original ask: Open Weights, Security, Coding, Claude,
  Kimi, Small Models, Harness

**Open assumption, not yet confirmed with user:** "retention" on a
pre-login landing page means enticing return visits / newsletter signup by
showing topic breadth — there's no auth session to track here. If the real
intent was logged-in engagement, boxes belong on `/feed`, not landing.

## Box definitions (verified against prod dump, 2026-07-26)

| slug | filter | live count |
|---|---|---|
| open-weights | tag = `Open Weights` | 65 |
| security | tag = `Security` | 87 |
| coding | tag = `Coding Assistants` | 185 |
| claude | tag = `Anthropic` | 208 |
| kimi | tag = `Kimi` OR title/publisher ILIKE `%kimi%`/`%moonshot%` | 17 tagged, ~25-30 padded |
| small-models | tag IN (`Model Distillation`, `Quantization`) OR title ILIKE `%tiny%`/`%distill%`/`%on-device%`/`%small model%`/`%edge%` | ~40-70 |
| harness | tag = `Orchestration` OR title ILIKE `%harness%`/`%terminal%`/`% cli %`/`%agentic loop%` | ~50+ |

No existing tag for `harness` or `claude`-as-such — `claude` maps to the
`Anthropic` tag (covers Claude models, Claude Code, MCP). `kimi` and
`harness` need keyword OR since tags don't cover them fully; this is plain
SQL ILIKE, not ML — fine per the "no semantic" decision above.

## Backend

**1. `app/api/topics.py`** — static `TOPICS: dict[str, TopicDef]` config.
`TopicDef` = tag names list + optional keyword list + optional kind. Keep
code-defined, no admin UI (see Not Doing).

**2. `GET /articles/topics/{slug}`** in `articles.py` — reuse
`build_rows`/`like_counts_subquery` from `article_view.py` (same as
`read_articles`). Build conditions: `Tag.name.in_(tags)` OR
`Article.title.ilike(...)` for each keyword, OR'd together. Sort
`score-desc`, `limit` default 6, param `?limit=`.
- 404 on unknown slug.

**3. `GET /articles/topics`** — list `[{slug, label}]` from the `TOPICS`
config, so frontend doesn't hardcode topic metadata twice. Cheap to add now,
avoids drift if topic list changes.

**4. Regenerate client** — `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts`,
commit per repo convention.

## Frontend

**5. `TopicBoxes.tsx`** replaces `SourceBoxes.tsx` in `LandingPage.tsx`.
Renders a grid of `TopicBox` components from `useQuery(['topics'])` (topic
list, long `staleTime` — this barely changes).

**6. `TopicBox` component** — one per box, own
`useQuery(['topic-articles', slug], () => ArticlesService.readArticlesByTopic({ slug, limit: 6 }))`.
Reuse card/list visual shell from current `SourceCard` (avatar, title,
tag chips, fade-on-overflow) — just swap the static `source.articles` data
source for the query result, and publisher avatar comes from
`article.publisher` now instead of hardcoded `source.domain`.

**7. Empty/thin box handling** — `kimi` and `harness` can run dry on slow
news days. If a box returns < 3 articles, either hide it that render or
show a lightweight "more soon" placeholder — don't ship an empty card.

## Not doing (v1)

- No admin UI for adding/editing topics — code change + deploy to add one
- No auto-trending / topic auto-discovery from embedding clusters
- No personalization — same 7 boxes for every visitor
- No semantic-search-backed boxes — flagged as future optional 8th box
  ("Trending this week"), not built now
- No topic-aware deep link into `/feed` — `/feed` filters are single-select
  tag/category/kind/publisher and can't represent OR'd keyword topics like
  `kimi`/`harness`/`small-models` cleanly. "See all" link deferred; if
  wanted later, cleanest path is a `topic` param on `/feed` + `ArticlesList`
  itself (mirrors the backend `/articles/topics/{slug}` filter), not
  client-side guessing
- No infinite scroll per box — fixed `limit`, newest-highest-score first
