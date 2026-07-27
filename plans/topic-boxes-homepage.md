# Topic lanes on landing page

Replace hardcoded `SourceBoxes` (static `sources.ts`, no db) with live
db-backed boxes. Each box = one topic, its own react-query.

**v1 is pure frontend — zero backend changes, zero migrations.** Goal is to
prove the concept and find out which boxes actually feel good before any
schema or endpoint work. v2 collapses each box to one request.

Global settings for every box: **sort by `published_at-desc`, limit 10,**
lazy-loaded on scroll.

## The test a box must pass

**A box earns its place only if it is worth a box.** Two families qualify:

- **Lanes** — combinations `/feed` cannot express (intersection, union,
  tag∩kind, editorial). These are the reason the page exists.
- **Presets** — a single filter, but a recognizable *format* or *lab*
  identity. Cheap, and their "see all" deep-links to `/feed` for free.

## v1: what the existing API can and cannot do

`readArticles` takes one `tag`, one `kind`, one `category`, one `publisher`,
`limit` ≤ 50, `sort`. Everything below was measured against the prod dump
**under date sort at limit 10** — the settings this plan actually ships.

**Works perfectly (1 request, server-side correct)**
Format presets and lab presets — one filter each.

**Works (N requests, merged client-side, provably correct)**
Union lanes and tag∩kind lanes. If article X is in the merged top-10 by
date, at most 9 articles in the merge are newer, so at most 9 are newer
within any single constituent query — X is therefore in that query's own
top-10. Verified on `open-challengers`: **10/10** of the true top-10
recovered. tag∩kind needs no client-side intersection at all, because `tag`
and `kind` travel in the *same* request.

**Broken — moved to v2**
tag∩tag lanes. Date sort has no ordering that constituent queries share, so
recall collapses:

| fetch limit | articles found | of true top-10 |
|---|---|---|
| 10 | **1** | 1/10 |
| 25 | 5 | 4/10 |
| 50 (API max) | 12 | 7/10 |

Under score sort this worked (6/6 at the top) because high-score articles
rank high in *every* tag's list. Date sort has no such shared spine — each
tag's recent items are its own. Even at the API ceiling it does not
recover, so `agent-security` and `claude-in-practice` cannot ship in v1.

**Broken — moved to v2**
Keyword lanes. `q` matches title **OR full article content**, so `q=harness`
returns 102 articles of which only 5 have "harness" in the title — 95% noise
(*"Ulysses Sequence Parallelism"*, *"Sarvam 105B"*). No title-only option
exists. `harness` and `small-models` ship tag-only in v1.

## Box set

Counts verified against dump 2026-07-26. `req` = v1 request cost.

### Lanes — v1

| box | type | query | n | req |
|---|---|---|---|---|
`pool` = articles matching the box. `fresh` = age of its newest article and
the span its 10 shown items cover. Every box fills all 10 slots.

| box | type | query | pool | fresh | req |
|---|---|---|---|---|---|
| harness | tag∩kind | (Orchestration\|Agents\|Coding Assistants) ∩ kind(repo, product) | 231 | 2d, 9d span | 6 |
| make-it-fast | ∪ | Inference Optimization\|Hardware\|Quantization\|Cost Optimization | 178 | 2d, 5d span | 4 |
| generative-media | ∪ | Multimodal\|Media Generation\|Voice & Speech | 145 | 3d, 8d span | 3 |
| small-models | ∪ | Model Distillation\|Quantization\|Local AI | 111 | 2d, 6d span | 3 |
| open-challengers | ∪ | Kimi\|DeepSeek\|Qwen\|GLM\|Mistral\|Llama | 75 | 6d, 7d span | 6 |
| open-model-drops | tag∩kind | `Open Weights` ∩ kind(model, announcement) | 36 | 5d, 34d span | 2 |

### Lanes — deferred to v2

| box | why |
|---|---|
| agent-security | tag∩tag — 1/10 recall under date sort. Best box in the set; worth waiting for the endpoint rather than shipping broken |
| claude-in-practice | tag∩tag — same |

Do **not** rescue these by widening to a union (`Security`∪`Safety`∪…) —
that drops the agent angle and collapses back to something `/feed` already
does in one click, failing the box test.

### Format presets — v1

| box | filter | pool | fresh | req |
|---|---|---|---|---|
| open-source-drops | kind=repo ∩ dev | 249 | 2d, 5d span | 1 |
| launches | kind=product ∩ dev | 170 | 2d, 12d span | 1 |
| new-models | kind=announcement ∩ models | 123 | 1d, 11d span | 1 |
| papers | kind=paper ∩ research | 49 | 11d, 13d span | 1 |

### Lab presets — v1

1 request each.

| box | pool | fresh |
|---|---|---|
| `Anthropic` | 208 | 3d, 8d span |
| `OpenAI` | 85 | 8d, 9d span |
| `Google` | 51 | 5d, 35d span |
| `Microsoft` | 21 | 14d, 19d span — marginal |
| `xAI` | 13 | 9d, **77d span** — cut |

**Cut `xAI`.** It fills 10 slots only by reaching back 77 days; a box whose
"latest" is from May reads as broken, not quiet. `Microsoft` is borderline
for the same reason — ship it only if the grid needs a 13th box.

**These must be tag-based, not publisher-based.** The db has 3 articles
*published by* Anthropic, 4 by Moonshot, 1 by xAI — the current homepage's
lab boxes are web-searched by `.agents/homepage-refresh.md`, not db-backed.
Tag coverage is rich (208) where publisher coverage is not. Swapping to
publisher would silently gut these boxes.

## Request budget

Two independent optimizations, both needed.

**1. Lazy load — only boxes in (or near) the viewport query at all.**
`IntersectionObserver` on each box wrapper drives react-query's `enabled`.
Use ~200px `rootMargin` so a box starts fetching just before it scrolls
into view rather than arriving blank. Once enabled, a box stays enabled —
never unmount its query on scroll-away, or scrolling up refetches
everything.

**Measured in a browser at 1280x900: 16 requests on first paint, 30 across a
full scroll.** Hero + newsletter push the grid down ~490px, cards are
`md:h-[26rem]`, so rows one and two both fall inside the viewport plus
`rootMargin` and load immediately.

Box *order* turned out to be the lever, not `rootMargin`. Ordering purely
best-first put the three widest lanes (harness 6, make-it-fast 4,
open-challengers 6) on top and cost **22** requests before any scroll;
leading with strong single-request boxes instead brought first paint to 16
with no loss of what a visitor sees first.

**2. Key queries by tag, not by box.** A box does not fetch "its" data — it
composes from `useQueries` over per-tag keys like
`['articles', {tag: 'quantization', sort: 'published_at-desc', limit: 10}]`.
Tags reused across boxes (`Quantization` is in both `make-it-fast` and
`small-models`; `Agents` and `Orchestration` recur in `harness`) then fetch
**once** and every later box reads the same cache entry — react-query
dedupes identical query keys for free. Each box still owns its own
`useQueries` declaration as intended. Confirmed in the browser: the 13 boxes
expand to 31 parts but issue **30** network requests — `quantization`, shared
by `make-it-fast` and `small-models`, is fetched once.

## Frontend

**1. `topics.ts`** — box definitions as plain data: `slug`, `label`,
`blurb`, `tagGroups` (OR within, AND across), `kinds`, `categories`. Pure
config, no fetching. Becomes the seed for v2's backend config.

**2. `useTopicArticles(def, enabled)`** — one hook. Expands a `TopicDef`
into per-tag `useQueries` (all `sort: 'published_at-desc'`, `limit: 10`),
merges by dedupe on id, re-sorts by `published_at desc`, slices to 10. All
v1 box types go through this one path.

**3. `TopicLanes.tsx`** replaces `SourceBoxes` in `LandingPage.tsx`.

**4. `TopicLane.tsx`** — reuse the `SourceCard` shell (avatar, scroll fade,
tag chips); swap `source.articles` for hook output, take the avatar from
`article.publisher` instead of a hardcoded domain.

**5. Fixed-height skeletons, always reserved.** With lazy loading the grid
must claim each box's height *before* its query runs, or every scroll tick
reflows the page under the user. Card is already `md:h-[26rem]` — keep it
and render skeleton rows inside.

**6. Thin boxes: show an empty state, do not unmount.** This reverses the
earlier "hide the box" rule, which is incompatible with lazy loading — a box
that vanishes *after* the user has scrolled to it yanks the content under
their cursor. Reserve the slot, and if a box comes back under 3 items,
render a quiet "nothing new here" inside it.

**7. "See all" — dropped from v1 entirely.** An earlier draft of this plan
claimed presets get it for free. They do not: `/feed`'s filters live in
`useState` inside `FiltersProvider` with no `validateSearch` on the route, so
**no feed filter has a URL at all**. Linking to `/feed` would land on the
unfiltered list. Making this work means putting feed filters in the URL —
worth doing, but it is its own task, not part of this one.

**8. Follow a box → newsletter.** `NewsletterSubscriber.categories` is
already free-form `list[str]` JSON, so
`subscribe({categories: ["open-challengers"]})` needs **no schema and no
backend change**. This is the retention loop — pick box, get email, come
back — and it is the main reason v1 is worth shipping before v2.

## v2: backend (deferred, not now)

Only once v1 says which boxes people actually use.

1. `app/api/topics.py` — the `topics.ts` config moved server-side
2. `GET /articles/topics` and `GET /articles/topics/{slug}` — one request per
   box, full tails, reusing `build_rows` + `like_counts_subquery`
3. **Unblocks `agent-security` and `claude-in-practice`** — tag∩tag done in
   SQL, where it is trivial
4. `topic` param on `read_articles`, plus URL-addressable `/feed` filters —
   together these make "see all" possible at all
5. Title-only keyword matching — unlocks the `harness` and `small-models`
   keyword halves
6. `CREATE INDEX ix_article_tag_tag_id ON article_tag(tag_id)` — current PK
   is `(article_id, tag_id)`, nothing leads on `tag_id`. Free at 2.4k rows;
   not free later
7. Regenerate client — `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts`

## Separate session: tag vocabulary gaps

**Hand this to an agent with VPS/prod access — it is not part of the box
work.** The vocabulary lives in the `tag` table (`backend/app/seed_tags.py`,
loaded by `backend/pipeline/tags.py`, fed to `AssignTags` in
`baml_src/tags.baml`). Adding a tag means seeding prod **and backfilling**
by re-running tagging over ~1,100 existing articles.

### Read this first — adding tags alone will not work

`AssignTags` is capped at **1-3 tags per article** against a 43-tag
vocabulary. That cap is why niche tags are already starving: `Llama` has 2
articles while Meta/Llama keywords match 34; `Quantization` 2,
`Cost Optimization` 2, `Sandboxing` 1. Specific tags lose to general ones
when only 3 slots exist. **Adding 8-14 more tags to the same cap will
dilute, not improve, coverage.** Fix the cap (or split vendor tags into
their own dimension) as part of the same change, and re-tag existing
articles — otherwise new tags land near-empty too.

### Gaps, by uncovered volume

Uncovered = title/summary matches the concept but the nearest existing tag
is absent.

| tag | mentions | uncovered | note |
|---|---|---|---|
| Benchmarks / Leaderboards | 86 | **58 (67%)** | biggest gap; `Evaluation` (60) misses SWE-bench/MMLU/arena |
| GPU / Compute | 78 | **51 (65%)** | `Hardware` (38) too narrow — CUDA/H100/TPU escaping |
| IDE / Editor | 31 | 13 | VS Code, Cursor, JetBrains |
| Claude Code | 116 | 11 | retrieval already fine, but 116 would rank ~5th largest; currently smeared across Anthropic + Coding Assistants |
| Inference Engines | 39 | 11 | vLLM, SGLang, llama.cpp, Ollama — sharper than `Local AI` |
| Skills / Subagents | 34 | 11 | emerging agent-composition primitive |
| MCP | 35 | 7 | a protocol, distinct thing, smeared into `Tool Calling` |
| MoE | 22 | 6 | |

**Vendor tags — taxonomy is inconsistent.** Google, Microsoft, OpenAI,
Anthropic, xAI, Mistral, DeepSeek, Kimi, Qwen, GLM are tagged; these are
not: Meta 34 · NVIDIA 33 · Hugging Face 30 · Cursor 20 · AWS 13 · Apple 11.

**Too thin, skip:** reasoning models 6 · computer use 5 · world models 5 ·
synthetic data 4 · vibe coding 4 · jobs 2.

**Editorial call, not a data question:** Regulation/Policy (12) and
Funding/Business (23) are invisible today. Probably right for a dev-focused
product, but they drive clicks.

**Worth a pipeline look, not a tag:** "reasoning model" matches only 6
articles. Low for 2026 — either ingest is not surfacing that vocabulary or
the tag set steers away from it.

## Known trade-offs

- **Date sort trades quality for freshness.** Measured on
  `generative-media`: top-10 by date averages score **86.6** and spans 8
  days; top-10 by score averages **99.4** and spans 9 months. Scores run
  76-100, so 86.6 is mid-high, not bad — and a news product that looks
  frozen is worse than one that looks merely good. Accepted, but this is the
  reason the two best-scoring boxes now look ordinary.
- **Boxes overlap and that is fine.** Per-box queries make cross-box dedupe
  impossible without a coordinating endpoint, which the one-query-per-box
  requirement rules out. An article in three boxes is a signal it is big.
- **Smaller boxes will look older.** `open-model-drops` has 36 articles
  total, so its 10 most recent span ~5 weeks. Nothing to fix, but expect
  uneven recency across the grid.
- **`published_at` is nullable in the schema but 0/1131 rows are null**, so
  date sort is safe today. Sort with `NULLS LAST` anyway.

## Not doing

- No admin UI for boxes — code change + deploy
- No auto-discovered/trending boxes — the co-occurrence lift analysis was a
  design tool run by hand, not a runtime feature
- No personalization — same boxes for everyone
- **No embedding-backed boxes.** `/articles/search` uses model2vec
  `potion-base-8M`, too weak to curate against, per explicit direction
- No freshness badge — dropped
- No source-identity boxes (Hacker News, digests, editor's picks) — dropped
- No time/quality boxes (top this week, perfect score, research desk) —
  dropped
- No per-box infinite scroll — fixed limit 10

## Follow-ups this work surfaced

- **`.agents/homepage-refresh.md` is now orphaned.** It exists to web-search
  each lab and open PRs editing `frontend/src/components/Home/sources.ts`,
  which this change deletes. Retire the agent or repoint it — as written its
  next run edits a file that no longer exists.
- **`/feed` filters need to be URL-addressable** before any box can offer
  "see all".
- **Backend does not boot on the pinned Python.** `.python-version` is
  `3.14`, the only interpreter uv offers here is `3.14.0rc2`, and pydantic
  2.13.4 calls `typing._eval_type(..., prefer_fwd_module=...)` which that RC
  does not accept. Unrelated to this change, but it blocks running the API
  locally.
