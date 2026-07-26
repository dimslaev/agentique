# Topic lanes on landing page

Replace hardcoded `SourceBoxes` (static `sources.ts`, no db) with live
db-backed topic lanes. Each lane = one curated topic, one react-query.

## What changed from v1 of this plan

v1 mapped each box to a single tag. Wrong — that is just the `/feed` filter
sidebar rearranged, and it ignored "don't base queries only on existing
tags". v1 also named retention as the goal but shipped no retention
mechanic. Both fixed below.

## The test a box must pass

**A box earns its place only if `/feed` filters cannot express it.**

`/feed` is single-select tag / category / kind / publisher. So `tag=Security`
is a chip, not a box — one click in the existing sidebar does it. A box must
be one of:

- **Intersection** — A AND B (`Security` ∩ `Agents`)
- **Supertopic union** — A OR B OR C (`Kimi`∪`DeepSeek`∪`Qwen`∪`GLM`)
- **Facet cross** — tag ∩ kind (`Open Weights` ∩ kind=`model`)
- **Editorial** — no tag exists, keyword/regex (`harness`, param-size regex)

Anything expressible as one filter gets cut.

## Lanes discovered from data, not guessed

Ran tag co-occurrence lift over the dump. Two strong clusters neither of us
named:

| pair | n | lift |
|---|---|---|
| Multimodal + Media Generation | 18 | 6.44 |
| Multimodal + Voice & Speech | 14 | 3.98 |
| Inference Optimization + Hardware | 16 | 3.11 |
| Coding Assistants + Anthropic | 57 | 1.68 |

→ **Generative Media** and **Make It Fast** added. The Anthropic+Coding lift
also says the "claude" lane should be Claude-*in-practice*, not all 208
Anthropic articles.

## Lane set (all counts verified against dump 2026-07-26)

| lane | type | query | n |
|---|---|---|---|
| agent-security | ∩ | (Security\|Safety\|Auditing\|Privacy\|Sandboxing) ∩ (Agents\|Tool Calling\|Browser Agents\|Orchestration) | 53 |
| open-model-drops | ∩ facet | `Open Weights` ∩ kind(model,announcement) | 36 |
| claude-in-practice | ∩ | `Anthropic` ∩ (Coding Assistants\|Prompt Engineering\|Orchestration) | 57 |
| open-challengers | ∪ | Kimi\|DeepSeek\|Qwen\|GLM\|Mistral\|Llama | 75 |
| harness | ∪∩ editorial | (Orchestration\|Agents\|Coding Assistants) ∩ kind(repo,product) + title `harness\|CLI\|terminal` | ~90 |
| small-models | ∪ editorial | (Model Distillation\|Quantization\|Local AI) ∪ param-size regex ∩ tiny/nano/edge/on-device | 117 |
| generative-media | ∪ | Multimodal\|Media Generation\|Voice & Speech | 145 |
| make-it-fast | ∪ | Inference Optimization\|Hardware\|Quantization\|Cost Optimization | 178 |

Bench (built if a lane above disappoints): `context-memory` (Agent Memory\|
Context Optimization\|RAG, 121), `papers` (kind=paper ∩ research, 49).

### Deviations from the requested list — read these

- **"security" → `agent-security`.** Bare `Security` (87) is a feed chip.
  Intersected with agents it becomes a topic that doesn't exist as a tag and
  is the hottest thing in the set. Sample: *"Declaw Arena — CTF-style
  challenge to break an AI agent in a microVM"*, *"Google SAIF: The Agent
  Security Map"*.
- **"kimi" → `open-challengers`.** Kimi alone is 17 articles — too thin to
  fill a lane on a slow week, and too narrow to be a lane anyone follows.
  Widened to the open-lab supertopic; Kimi is still the headline inside it.
- **"coding" cut as standalone.** `Coding Assistants` is the 3rd-largest tag
  and lands inside both `claude-in-practice` and `harness`. A separate
  Coding box would be ~70% duplicate of those two. Cut, not forgotten.
- **"static models" → `small-models`,** per "8m params not gpt". Verified:
  *"Granite 4.0 1B Speech"*, *"Nemotron 3 Nano 4B"*, *"Gemma 2B runs on
  laptop CPU"*.

## Retention mechanic — the actual point

v1 had none. A grid of links is a shelf; a shelf does not bring anyone back.
Three additions, cheapest first:

**1. Freshness badge.** Each lane returns `new_count` = matches published in
last 7d. Header shows "4 new this week". Without a reason to look *now*, a
returning visitor sees the same grid as last time and leaves.

**2. Follow a lane → newsletter.** `NewsletterSubscriber.categories` is
already free-form `list[str]` JSON. Subscribing to a lane is
`subscribe({categories: ["agent-security"]})` — **zero schema change, zero
backend change.** This is the real return loop: pick lane → get email → come
back. Biggest value-per-effort in this plan.

**3. "See all" → feed.** A lane you cannot expand past 6 items is a dead
end. Needs a `topic` param on `read_articles` reusing the exact same
condition builder as the lane endpoint. Last item, cuttable, but a box
without it leaks users.

## Backend

**1. `app/api/topics.py`** — declarative config, boxes are data not code:

```python
@dataclass(frozen=True)
class TopicDef:
    slug: str
    label: str
    blurb: str
    tag_groups: list[list[str]] = []   # OR within group, AND across groups
    kinds: list[str] = []
    title_any: list[str] = []          # OR'd against tag_groups
    categories: list[str] = []
```

One `build_conditions(TopicDef)` helper turns it into SQLAlchemy. Every lane
above is expressible in it — that is the schema's acceptance test.

**2. `GET /articles/topics/{slug}`** — reuse `build_rows` +
`like_counts_subquery` from `article_view.py` (same path `read_articles`
uses, so lanes get like counts and `liked_by_me` free). `limit` default 6,
sort score desc. 404 unknown slug.

**3. `GET /articles/topics`** — `[{slug, label, blurb, count, new_count}]`.
Frontend renders the grid from this, so lane metadata lives in one place.

**4. `topic` param on `read_articles`** — same condition builder, for "see
all". (Retention item 3.)

**5. `CREATE INDEX ix_article_tag_tag_id ON article_tag(tag_id)`** — alembic
migration. Current PK is `(article_id, tag_id)`, so nothing leads on
`tag_id`, and every lane query filters on it. Free at 2.4k rows, not free at
8 concurrent lane queries as the corpus grows.

**6. Regenerate client** — `types.gen.ts`, `sdk.gen.ts`, `schemas.gen.ts`,
commit (repo convention).

## Frontend

**7. `TopicLanes.tsx`** replaces `SourceBoxes` in `LandingPage.tsx`.
`useQuery(['topics'])` for the lane list, long `staleTime`.

**8. `TopicLane.tsx`** — one per lane, own query as specified:
`useQuery(['topic', slug], () => ArticlesService.readTopic({slug, limit: 6}))`.
Reuse the `SourceCard` shell (avatar, scroll fade, tag chips); swap
`source.articles` for query data and take the avatar from
`article.publisher` instead of a hardcoded domain.

**9. Skeleton per lane.** 8 independent queries resolve at different times.
Without fixed-height skeletons the grid reflows 8 times on load. Card is
already `md:h-[26rem]` — keep that, render skeleton rows inside.

**10. Thin-lane guard.** Under 3 results → hide the lane this render rather
than ship an empty card.

## Known trade-offs

- **Lanes overlap and that is fine.** *Declaw Arena* is in both
  `agent-security` and `harness`; *Kimi Work* in both `open-challengers` and
  `harness`. Independent per-lane queries make cross-lane dedupe impossible
  without a coordinating endpoint, which the one-query-per-box requirement
  rules out. Accepted: an article in three lanes is a signal it is big, not
  a bug.
- **No hard weekly windows.** Only 44 articles in the last 7d vs 290 in 30d.
  8 lanes × 6 slots = 48 > 44, so a strict 7d filter starves the grid. Lanes
  rank all-time by score; recency shows up in the `new_count` badge instead.
- **8 requests on landing.** Explicitly requested (one query per box). Cheap
  and cacheable, but it is 8 round trips before the page settles.

## Not doing (v1)

- No admin UI for lanes — code change + deploy to add one
- No auto-discovered/trending lanes — lift analysis was a design tool, run
  by hand, not a runtime feature
- No personalization — same lanes for everyone
- **No embedding-backed lanes.** `/articles/search` uses model2vec
  `potion-base-8M`; too weak to curate against, per explicit direction. The
  hnsw index stays unused here.
- No per-lane infinite scroll — fixed limit, "see all" goes to feed

## Unresolved

`min_score` on `read_articles` validates `ge=1, le=10` but actual scores are
76–100, so the param can never match. Pre-existing, unrelated to lanes,
flagged for whenever someone touches that endpoint.
