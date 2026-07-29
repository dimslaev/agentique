# RSS category-filter pipeline

**Status: implemented.** This doc is the design record; the code is the truth.

Old pipeline: fetch → prefilter → dedup → score 1-100 → insert → summarize →
categorize (dev/models/research) → tag (43-tag vocabulary) → embed. The
homepage then reassembled lanes from tag unions and tag∩kind crosses in
frontend TS.

New pipeline: fetch → two static gates → dedup → **does this article match one
of 9 categories?** → insert only if yes, with the categories attached. Lane =
`where category_id = X order by published_at desc`. No score, no tags, no
dev/models/research enum.

The category list stops being a *view* over the corpus and becomes the *filter
that defines* it.

## The 9 categories

Orthogonal by construction — each answers a different question:

| Category | The question it answers |
|---|---|
| Model Releases | Was a new model released? |
| Open Weights | Can developers download the weights? |
| Local AI | Can developers run it on their own hardware? |
| Coding Agents | Is it about AI for software development? |
| Tool Use & MCP | Can the model invoke external software? |
| RAG | Does it retrieve knowledge into the context? |
| Multimodal | Is a non-text modality the point? |
| Inference & Optimization | Does it make AI faster, smaller, or cheaper? |
| Security & Safety | Is something going wrong, or being stopped? |

### Why there is no AI Labs category

It shipped in the first cut and was removed. The measurement that settled it:
365 articles in the dump matched AI Labs, but **293 of them already matched
another category** — so it uniquely held only **72**, and those 72 are pure
corporate news (funding, pricing, acquisitions, leadership). The old scorer
explicitly bottom-tiered exactly that content.

Removing it and adding RAG, Multimodal and Security & Safety **raised** corpus
coverage from 78% to 85%. Narrower beat, more of the corpus with a home — the
"AI Labs is 32% of the corpus" figure was measuring lane *overlap*, not unique
contribution.

Voice, vision and cross-modal are one category rather than three. Separately
they were the overlap problem in the original 17-topic sketch (Multi Modal ate
both single-modality lanes); together they are 145 articles and one clean
question.

Definitions live in `backend/app/data/categories.json` → the `category` table.
The `description` field *is* the prompt, so vagueness in it is a bug. Editing a
description changes what gets ingested from that point on; the back catalogue
was filtered under the old wording.

Up to 3 categories per article. Zero categories = not stored.

### What this drops

Nothing outside those 9 gets in. Measured on the prod dump by mapping the old
43-tag vocabulary onto the new categories, ~15% of the corpus (165 of 1131) has
no home. Biggest remaining orphans: `enterprise-ai` 70, `evaluation` 60,
`context-optimization` 41, `fine-tuning` 32, `prompt-engineering` 26,
`robotics` 22 — plus the 72 pure-corporate-news articles AI Labs used to hold.

Deliberate. The site gets smaller and much more focused.

## Measurements that shaped it

Proxy-mapped on the prod dump (1131 articles, 43 tags, 2.14 tags/article):

- **Lane sizes**: Tool Use 192, Inference 190, Coding Agents 185,
  Security & Safety 155, Multimodal 145, Model Releases 131, Open Weights 125,
  Local AI 110, RAG 87. No thin lanes — the smallest is still 4x the size that
  killed Sovereign AI in the original sketch.
- **The 3-category cap barely binds**: 52 of 877 articles reach 3, 4 reach 4.
  It is a guard against a padding model, not a routine constraint.
- **Lanes overlap more than the taxonomy implies**: 25% of Open Weights is also
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
name + description + ~10 exemplar phrases. Per article, cosine against all of
them; below the floor, drop.

Prototypes are computed per run, not stored. Nine encodes cost nothing, and a
stored vector could go stale against an edited description — the failure mode
where a category quietly stops matching.

No top-k shortlisting. That was in the original 17-topic sketch to keep the
prompt small; at this size the whole vocabulary fits, and shortlisting would
only add a recall risk for no saving.

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

`improve_titles` and `embed_articles`. That is it — one LLM call after insert,
batched, for titles.

### The excerpt replaced the summary

There was a `Summarize` call, one per article, producing the card text and the
article's `kind`. Both are gone from the LLM path:

- **Card text** is now `pipeline/excerpt.py` — a sanitized slice of the
  article's own opening. Strips HTML and entities (two passes, because feeds
  double-escape), fenced code, markdown, emoji, README banner art
  (`\u2500-\u259F`, 290 occurrences in the dump), and zero-width characters;
  collapses whitespace; trims to `EXCERPT_CHARS` on a word boundary. Pure and
  deterministic.

  Worse text, better properties. An excerpt is the article's opening rather
  than its point — but it is free, it cannot invent anything, and its failure
  mode (a truncated sentence) is visibly ugly rather than quietly wrong. The
  summarizer's failures were the quiet kind: echoed markdown, leaked CJK, its
  own JSON envelope — all of which the title-rewriter then copied into titles.

  CJK is deliberately kept. The old summarizer rejected it as corruption
  because the *model* was drifting out of English; an excerpt only repeats the
  source, so a Chinese article reads as Chinese.

- **`kind`** rides on the `MatchCategories` response instead, costing no extra
  call. It stays a hint: `persist.resolve_kind` prefers the URL host when that
  is conclusive (github → repo, arxiv → paper, hf → model), and a blog that
  links a repo is a repo.

The `summary` column is renamed `excerpt` and keeps its text, so pre-migration
rows still show their old summaries. `scripts/backfill_excerpts.py` regenerates
them from stored content — no LLM, safe to re-run after tuning the sanitizer.

## Retiring a category

`seed_categories` deactivates categories missing from `categories.json` rather
than deleting them, so `article_category` rows survive and the change is
reversible by putting the entry back. Everything user-facing filters on
`is_active`: no lane, no facet, no chip on a card, and a stale `?category=`
link returns nothing rather than a corner of the archive no link points at.

That is how AI Labs was removed — no migration, no data loss.

## Schema

```
category(id, slug, name, description, exemplars json, position, is_active)
article_category(article_id, category_id)     -- <= 3 rows per article
```

Dropped: `article.score`, `article.categories` (the dev/models/research JSON),
`tag`, `article_tag`. Renamed: `article.summary` -> `article.excerpt`.

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
