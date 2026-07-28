# RSS category-filter pipeline

**Status: implemented.** This doc is the design record; the code is the truth.

Old pipeline: fetch → prefilter → dedup → score 1-100 → insert → summarize →
categorize (dev/models/research) → tag (43-tag vocabulary) → embed. The
homepage then reassembled lanes from tag unions and tag∩kind crosses in
frontend TS.

New pipeline: fetch → two static gates → dedup → **does this article match one
of 7 categories?** → insert only if yes, with the categories attached. Lane =
`where category_id = X order by published_at desc`. No score, no tags, no
dev/models/research enum.

The category list stops being a *view* over the corpus and becomes the *filter
that defines* it.

## The 7 categories

Orthogonal by construction — each answers a different question:

| Category | The question it answers |
|---|---|
| AI Labs | Who did it? |
| Model Releases | Was a new model released? |
| Open Weights | Can developers download the weights? |
| Coding Agents | Is it about AI for software development? |
| Tool Use & MCP | Can the model interact with external tools? |
| Local AI | Can developers run it on their own hardware? |
| Inference & Optimization | Does it improve speed, efficiency, or cost? |

Definitions live in `backend/app/data/categories.json` → the `category` table.
The `description` field *is* the prompt, so vagueness in it is a bug. Editing a
description changes what gets ingested from that point on; the back catalogue
was filtered under the old wording.

Up to 3 categories per article. Zero categories = not stored.

### What this drops

Nothing outside those 7 gets in. Measured on the prod dump by mapping the old
43-tag vocabulary onto the new categories, ~22% of the corpus (254 of 1131)
has no home — and that is the *generous* estimate, since the tag proxy is
looser than a strict LLM match. Biggest orphans: `multimodal` 117,
`security` 87, `evaluation` 60, `rag` 48, `voice-speech` 34, `robotics` 22.

Deliberate. The site gets visibly smaller and much more focused.

## Measurements that shaped it

Proxy-mapped on the prod dump (1131 articles, 43 tags, 2.14 tags/article):

- **Lane sizes**: AI Labs 365, Tool Use 192, Inference 190, Coding Agents 185,
  Model Releases 131, Open Weights 125, Local AI 110.
- **AI Labs is 32% of the corpus** and, as defined, a catch-all — funding,
  pricing, acquisitions, leadership. The old scorer explicitly bottom-tiered
  that content (`31-40: Funding rounds without product details`). It is placed
  last in lane order for this reason.
- **The 3-category cap barely binds**: 52 of 877 articles reach 3, 4 reach 4.
  It is a guard against a padding model, not a routine constraint.
- **Lanes overlap more than the taxonomy implies**: 49% of Model Releases is
  also AI Labs; 35% of Tool Use is also AI Labs; 25% of Open Weights is also
  Model Releases. Orthogonal *definitions*, correlated *content*. The lane UI
  shows an article's other categories, which turns that overlap into
  cross-links rather than noise.

## The cascade

Cheapest-first, each gate seeing only what the previous could not rule out.

### Gate 0 — keep/drop classifier (free, unchanged)

`pipeline/keep_drop.py`: logistic regression over `potion-base-8M`, 256-d,
distilled from gpt-oss, threshold 0.15 at ~0.99 recall. Answers "is this AI
developer news at all". This *is* the static potion-8M filter — it already
existed and already runs first.

### Gate 1 — static category floor (`potion-base-8M`, no LLM)

Per category, a **prototype vector**: the mean embedding of
name + description + ~10 exemplar phrases. Per article, cosine against all 7;
below the floor, drop.

Prototypes are computed per run, not stored. Seven encodes cost nothing, and a
stored vector could go stale against an edited description — the failure mode
where a category quietly stops matching.

No top-k shortlisting. That was in the original 17-topic sketch to keep the
prompt small; with 7 categories the whole vocabulary fits, and shortlisting
would only add a recall risk for no saving.

**Ships disabled (`CATEGORY_GATE_THRESHOLD=0`).** The right floor is a property
of the embedding model and the category wording, and guessing it means silently
deleting articles the matcher would have accepted, with no trace beyond a
`ScoredUrl` row. `backend/scripts/calibrate_category_gate.py` prints the recall
curve against a restored dump; set the env var from that. Gate 0 runs
regardless, so the cheap-static-then-LLM cascade holds either way.

### Gate 2 — `MatchCategories` (LLM, batched)

One call per 8 articles; the vocabulary travels once per batch. Output is
0-3 slugs per article, validated against the vocabulary — off-list slugs are
dropped and nothing is minted at runtime.

Three things the prompt is built around:
- **Empty is a normal answer.** "Rejecting an article is the normal outcome,
  not a failure."
- **Primary subject, not keyword.** A passing mention of Cursor does not make a
  post about org design a Coding Agents story.
- **Worked examples**, including three that must come back empty.

A batch that errors is *not* recorded in `ScoredUrl`, so those articles are
retried next run. A provider timeout must not silently blacklist good articles.

## What survivors still get

`improve_titles`, `Summarize` (summary + kind), `embed_articles`. Summaries
stay — the cards are unreadable without them, and it is the only per-article
LLM call left after insert.

## Schema

```
category(id, slug, name, description, exemplars json, position, is_active)
article_category(article_id, category_id)     -- <= 3 rows per article
```

Dropped: `article.score`, `article.categories` (the dev/models/research JSON),
`tag`, `article_tag`.

Migration `c3d4e5f6a7b8`. Destructive — the tag vocabulary and every score go
with it. Existing articles survive uncategorised until
`scripts/backfill_categories.py` runs; that script deliberately does *not*
delete articles that match nothing, and reports the count instead. That number
is the honest measure of how much of the old corpus the new filter would have
refused.

## Read side

`GET /articles?category=<slug>` is one indexed join
(`ix_article_category_category_id`). `GET /articles/categories` returns the
vocabulary in `position` order, including empty lanes.

The frontend's `TopicDef` union/cross machinery is gone: `useTopicArticles` is
one `useQuery`, and the lane list comes from the server, so re-ordering the
homepage is a DB update rather than a deploy. The tag∩tag lanes that v1 could
not express correctly (see `plans/topic-boxes-homepage.md`) work by
construction now — the intersection was decided at ingest.

## Risks

- **A dropped article is gone.** Previously a mis-scored article still landed in
  `/feed`. Now, no category = never stored. `ScoredUrl` keeps the URL so a
  rejection can be audited, but the judgement is not replayable without a
  refetch.
- **AI Labs will dominate.** 32% of the corpus and the least technical of the
  seven. If it swamps the homepage, tighten its description to exclude pure
  funding/personnel news — that is a DB edit, not a deploy.
- **Definition drift.** Retuning a description changes ingestion going forward
  only. Version the change and note the cutover.
- **Gate 1 is unproven.** It ships off. Calibrate before enabling, and check the
  titles it would drop read as off-beat rather than merely unusual.
- **Volume.** ~60 genuinely new articles per run across 7 categories, before
  filtering. A stricter filter than `score >= 76` means fewer inserts; watch the
  `unmatched` counter in the run report for the first week.
