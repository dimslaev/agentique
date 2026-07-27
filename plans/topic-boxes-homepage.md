# Topic lanes on landing page

Replace hardcoded `SourceBoxes` (static `sources.ts`, no db) with live
db-backed boxes. Each box = one topic, its own react-query.

**v1 is pure frontend — zero backend changes, zero migrations.** Goal is to
prove the concept and find out which boxes actually feel good before any
schema or endpoint work. v2 collapses each box to one request.

## The test a box must pass

**A box earns its place only if it is worth a box.** Two families qualify:

- **Lanes** — combinations `/feed` cannot express (intersection, union,
  tag∩kind, editorial). These are the reason the page exists.
- **Presets** — a single filter, but a recognizable *format* or *lab*
  identity. Cheap, and their "see all" deep-links to `/feed` for free.

## v1: what the existing API can and cannot do

`readArticles` takes one `tag`, one `kind`, one `category`, one `publisher`,
`limit` ≤ 50, `sort`. Everything below was measured against the prod dump.

**Works perfectly (1 request, server-side correct)**
Format presets and lab presets — one filter each.

**Works (N requests, merged client-side, correct at limit 6)**
Union lanes. Union of per-tag top-50s trivially contains the union's top 6.

**Works (N×M requests, each server-side correct)**
tag∩kind lanes — `tag` and `kind` go in the *same* request, so no client-side
intersection is needed at all.

**Degraded but acceptable (client-side intersection)**
tag∩tag lanes. Measured on `agent-security`: the true intersection is 53
articles, client-side recovery is **15**. But the **top 6 by score came back
6/6** — high-score articles are in every tag's top-50 by construction. Fine
for a 6-item box, breaks the moment anyone expands it.

**Broken — cut from v1**
Keyword lanes. `q` matches title **OR full article content**, so `q=harness`
returns 102 articles of which only 5 have "harness" in the title — 95% noise
(*"Ulysses Sequence Parallelism"*, *"Sarvam 105B"*). No title-only option
exists. `harness` and `small-models` therefore ship tag-only in v1 and pick
up their keyword half in v2.

## Box set

Counts verified against dump 2026-07-26. `req` = v1 request cost.

### Lanes

| box | type | query | n | req |
|---|---|---|---|---|
| agent-security | ∩ | (Security\|Safety\|Auditing\|Privacy\|Sandboxing) ∩ (Agents\|Tool Calling\|Browser Agents\|Orchestration) | 53 | 9 |
| claude-in-practice | ∩ | `Anthropic` ∩ (Coding Assistants\|Prompt Engineering\|Orchestration) | 57 | 4 |
| open-model-drops | tag∩kind | `Open Weights` ∩ kind(model, announcement) | 36 | 2 |
| harness | tag∩kind | (Orchestration\|Agents\|Coding Assistants) ∩ kind(repo, product) | ~90 | 6 |
| open-challengers | ∪ | Kimi\|DeepSeek\|Qwen\|GLM\|Mistral\|Llama | 75 | 6 |
| generative-media | ∪ | Multimodal\|Media Generation\|Voice & Speech | 145 | 3 |
| make-it-fast | ∪ | Inference Optimization\|Hardware\|Quantization\|Cost Optimization | 178 | 4 |
| small-models | ∪ | Model Distillation\|Quantization\|Local AI | 117 | 3 |

### Format presets

| box | filter | n | req |
|---|---|---|---|
| papers | kind=paper ∩ research | 49 | 1 |
| open-source-drops | kind=repo ∩ dev | 249 | 1 |
| launches | kind=product ∩ dev | 170 | 1 |
| new-models | kind=announcement ∩ models | 123 | 1 |

### Lab presets

`Anthropic` 208 · `OpenAI` 85 · `Google` 51 · (`Microsoft` 21, `xAI` 13 —
thin, optional). 1 request each.

**These must be tag-based, not publisher-based.** The db has 3 articles
*published by* Anthropic, 4 by Moonshot, 1 by xAI — the current homepage's
lab boxes are web-searched by `.agents/homepage-refresh.md`, not db-backed.
Tag coverage is rich (208) where publisher coverage is not. Swapping to
publisher would silently gut these boxes.

## v1 request budget — read this before building

Everything above is ~44 requests on landing page load. That is the honest
cost of proving the concept with no backend.

**Mitigation: key the queries by tag, not by box.** A box does not fetch
"its" data — it composes from `useQueries` over per-tag keys like
`['articles', {tag: 'agents', limit: 50}]`. Tags reused across boxes
(`Agents`, `Orchestration`, `Quantization`) then fetch **once** and every box
reads the same cache entry — react-query dedupes identical query keys for
free. Distinct tags across all lanes ≈ 20, plus 4 format presets and 3 lab
presets, so **~27 requests instead of 44**, and each box still owns its own
`useQueries` declaration as intended.

Trim further by dropping boxes, not by batching — batching is v2's job.

## Frontend

**1. `topics.ts`** — box definitions as plain data: `slug`, `label`,
`blurb`, `tagGroups` (OR within, AND across), `kinds`, `categories`. Pure
config, no fetching. Becomes the seed for v2's backend config.

**2. `useTopicArticles(def)`** — one hook. Expands a `TopicDef` into
per-tag `useQueries`, then merges: union = dedupe by id, intersection =
filter by id presence across groups, then sort by score and slice to 6.
All box types go through this one path.

**3. `TopicLanes.tsx`** replaces `SourceBoxes` in `LandingPage.tsx`.

**4. `TopicLane.tsx`** — reuse the `SourceCard` shell (avatar, scroll fade,
tag chips); swap `source.articles` for hook output, take the avatar from
`article.publisher` instead of a hardcoded domain.

**5. Fixed-height skeletons.** Boxes resolve at different times; the card is
already `md:h-[26rem]`, keep it and render skeleton rows inside so the grid
does not reflow N times on load.

**6. Thin-box guard.** Under 3 results → hide the box this render rather
than ship an empty card.

**7. "See all" — presets only in v1.** A preset is one filter, so it
deep-links straight into `/feed` with existing params. Lanes have no URL
that can represent them until v2; omit the link on lanes rather than send
users somewhere that shows the wrong thing.

**8. Follow a box → newsletter.** `NewsletterSubscriber.categories` is
already free-form `list[str]` JSON, so
`subscribe({categories: ["agent-security"]})` needs **no schema and no
backend change**. This is the retention loop — pick box, get email, come
back — and it is the main reason v1 is worth shipping before v2.

## v2: backend (deferred, not now)

Only once v1 says which boxes people actually use.

1. `app/api/topics.py` — the `topics.ts` config moved server-side
2. `GET /articles/topics` and `GET /articles/topics/{slug}` — one request per
   box, full tails, reusing `build_rows` + `like_counts_subquery`
3. `topic` param on `read_articles` — makes "see all" work for lanes
4. Title-only keyword matching — unlocks the `harness` and `small-models`
   keyword halves that v1 cannot do
5. `CREATE INDEX ix_article_tag_tag_id ON article_tag(tag_id)` — current PK
   is `(article_id, tag_id)`, nothing leads on `tag_id`. Free at 2.4k rows;
   not free later
6. Regenerate client — `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts`

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

- **Boxes overlap and that is fine.** *Declaw Arena* is in both
  `agent-security` and `harness`. Per-box queries make cross-box dedupe
  impossible without a coordinating endpoint, which the one-query-per-box
  requirement rules out. An article in three boxes is a signal it is big.
- **No time windows.** Only 44 articles in the last 7d vs 290 in 30d, so a
  weekly filter would starve a multi-box grid. Boxes rank all-time by score.
- **v1 intersections show the head, not the tail** — 6/6 correct at the top,
  ~28% recall overall. Acceptable at limit 6; the reason "see all" is
  preset-only until v2.

## Not doing

- No admin UI for boxes — code change + deploy
- No auto-discovered/trending boxes — the co-occurrence lift analysis was a
  design tool run by hand, not a runtime feature
- No personalization — same boxes for everyone
- **No embedding-backed boxes.** `/articles/search` uses model2vec
  `potion-base-8M`, too weak to curate against, per explicit direction. The
  hnsw index stays unused here
- No freshness badge — dropped
- No source-identity boxes (Hacker News, digests, editor's picks) — dropped
- No time/quality boxes (top this week, perfect score, research desk) —
  dropped
- No per-box infinite scroll — fixed limit
