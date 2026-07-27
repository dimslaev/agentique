# RSS topic-filter pipeline

Idea sketch for a *second* project. No code changes here.

Today: fetch → prefilter → dedup → score 1-100 → insert → summarize →
categorize → tag (43-tag vocabulary) → embed. Homepage then reassembles
lanes out of tag unions and tag∩kind crosses (`frontend/src/components/Home/topics.ts`).

Proposed: fetch RSS → **does this article belong to one of our N topics?** →
insert only if yes, with the topic attached. Lane = `where topic_id = X order
by published_at desc`. No score, no tags, no category, no join gymnastics.

The topic list stops being a *view* over the corpus and becomes the
*filter that defines* the corpus.

## Why the flip

Measured on the prod dump (1131 articles, 43 tags, 2.14 tags/article):

- Scoring is a **global** relevance axis; topics are **local**. An article can
  score 85 and still belong to no lane. Today that article is stored anyway —
  it lands in `/feed` and nowhere else.
- The current homepage compensates with unions of 4-6 tags
  (`open-challengers`, `make-it-fast`) because no single tag is a lane. That's
  a lane definition living in frontend TS, evaluated at request time, 30
  requests per page load.
- Tag distribution is very long-tailed: `agents` 302, `anthropic` 208,
  `coding-assistants` 185 … `sandboxing` 1, `quantization` 2, `llama` 2. The
  tail tags cost an LLM call per article to assign and back no lane.
- Asking "match?" per topic is a **cheaper and more precise** question than
  "rate 1-100" + "pick ≤3 of 43 tags". Binary, defined by a written topic
  description, testable.

## Topics (17)

Human-readable, lane-sized. Each needs a written definition — the definition
*is* the filter prompt, so vagueness is a bug.

| Topic | Rough corpus size today |
|---|---|
| AI Labs | ~380 (openai 85 + anthropic 208 + google 51 + xai 13 + microsoft 21) |
| Open Weights | ~140 (open-weights 65 + kimi/deepseek/qwen/glm/mistral/llama 76) |
| Sovereign AI | ~23 keyword hits — **thin, see risks** |
| Local AI | 92 |
| Small Models | ~77 keyword hits (distill 20 + quantization 2 tagged) |
| Multi Modal | 117 |
| Visual AI | ~120 keyword hits |
| Voice AI | ~71 keyword hits (voice-speech tag 34) |
| RAG | 90 (rag 48 + agent-memory 42) |
| Robotics | 22 |
| Research | 52 (`kind=paper`) |
| Coding Agents | ~192 keyword hits (coding-assistants 185) |
| Fast Inference | 191 (inference-optimization 153 + hardware 38) |
| Security & Safety | 137 (security 87 + safety 38 + sandboxing 1 + privacy 11) |
| Tool Use & MCP | 101 |
| Evals & Benchmarks | 60 |
| Model Releases | 131 |

Added beyond the original list: **Tool Use & MCP**, **Evals & Benchmarks**,
**Model Releases** — each is >60 articles and has no home otherwise.

Deliberately *not* a topic: **Agents**. It's the biggest tag (302) and it is
the whole site — as a lane it would swallow half the corpus. Same reason
`orchestration` (88) and `enterprise-ai` (70) stay out.

### Overlaps that must be resolved in the definitions

The LLM will smear across these unless the prompt says which wins:

- **Multi Modal vs Visual AI vs Voice AI** — Visual and Voice are the
  single-modality lanes (image/video model, TTS/ASR/voice agent). Multi Modal
  is only for *cross*-modal systems. Otherwise Multi Modal eats both.
- **Small Models vs Local AI vs Open Weights** — Small = the model is small
  (params/distilled/quantized). Local = it *runs on your machine*. Open
  Weights = the weights shipped. A 4B open-weight local model is all three,
  and that's fine; but "Ollama adds a feature" is Local only.
- **AI Labs vs Model Releases** — Model Releases is the *format* (a release
  happened). AI Labs is the *actor*. A GPT-5 launch is both.
- **Fast Inference vs Small Models** — quantization is Small when it's about
  the artifact, Fast Inference when it's about serving throughput/latency.

Multi-topic is allowed (cap 3, same as today's tag cap). Zero topics = the
article is dropped. That drop is the point.

## The cascade

Three gates, cheapest first — same shape as today's `prefilter_keep_drop` →
`ScoreArticles`, one stage deeper.

### Gate 0 — keep/drop classifier (free, reuse as-is)

`pipeline/keep_drop.py` already exists: logistic regression over
`potion-base-8M`, 256-d, distilled from gpt-oss, threshold 0.15 at ~0.99
recall. Kills obvious non-AI junk with no LLM call. Unchanged.

### Gate 1 — static topic gate (potion-base-8M, no LLM)

Per topic, a **prototype vector**: mean of `potion-base-8M` embeddings of
(topic name + description + 5-10 hand-picked exemplar articles). Stored on the
topic row, recomputed only when the definition changes.

Per article, cosine against all 17 prototypes:

- max sim below `drop_below` → **drop**, no LLM call, record in `scored_url`.
- else → shortlist the **top-k topics (k≈4)** above `shortlist_at`.

Two jobs in one pass, and the second is the bigger win: the LLM never judges
17 topics, it judges the 4 plausible ones. Prompt size drops ~4×, and the
model stops pattern-matching against topics that were never in play.

Same model as gate 0, so it's one `encode()` call for the batch — the vectors
are already in memory.

### Gate 2 — LLM topic match (batched)

One call per batch of ~8 articles. Input: title + snippet + each article's
shortlisted topic definitions. Output: per article, the subset of the
shortlist it actually belongs to (possibly empty).

- Batch of 8, not 5 — the per-article payload is smaller than today's scoring
  prompt because only 4 topic definitions travel with it.
- Same `Nvidia` fallback chain (Gemini → gpt-oss → Ministral).
- Post-validate against the topic slug set, exactly like `tags.normalize_tag`
  does today. Off-list output is dropped, never minted.
- Empty output is a **valid, expected** answer. Today a missing score means
  reject; here a missing topic means reject. Same rule, kept.

### What happens to the survivors

Summaries stay (needed for the card). Everything else — `score`, `categories`,
the 43-tag vocabulary, `article_tag` — goes away. `kind` may survive as a
format facet if the Research lane wants `paper` for free; otherwise it goes
too.

## Calibration — the part the dump makes possible

Do not guess the two thresholds. The dump is a labeled-ish set:

1. Hand-label ~300 articles from the dump against the 17 definitions (the
   existing tags give a strong prior — `voice-speech` → Voice AI, etc.).
2. Sweep `drop_below` and `shortlist_at` over that set.
3. Target **recall ≥ 0.98 at gate 1**. Gate 1 must never be the thing that
   loses an article — that's the same posture `keep_drop` already takes
   ("deliberately low, high recall"). Precision is gate 2's job.
4. Report per-topic recall. A topic whose prototype can't hit 0.98 has a bad
   definition, not a bad threshold.

Also worth measuring on the dump: how many of the 1131 stored articles match
**zero** topics. That number is the feature — it's what the new pipeline would
never have stored.

## Cost

Per run today (from `pipeline_run.sources`): ~130-200 fetched, ~50-70 new
after `filtered_known`. Those ~60 currently cost 1 dedup call + ~12 scoring
batches + 4 calls per *inserted* article (title, summarize+categorize, tags,
embed).

New: 1 dedup call + ~8 topic-match batches + 1 summarize per survivor.
Survivors should be **fewer** than today's inserts — a precise 17-topic filter
is stricter than `score ≥ threshold`. Rough net: fewer calls, and the
remaining ones carry smaller prompts.

## Schema sketch

```
topic(id, slug, name, description, prototype vector(256), is_active)
article_topic(article_id, topic_id)     -- ≤3 rows per article
```

`topic.description` is the prompt text — same pattern as `tag.description`
feeding `AssignTags` today. Editing a lane is a DB update, not a deploy.
Changing a description invalidates that topic's prototype vector.

Homepage lane becomes one request: `readArticles(topic=slug, limit=10,
sort=published_at-desc)`. The whole `TopicDef` union/cross machinery in
`topics.ts` deletes, and the tag∩tag lanes that v1 couldn't express (see
`plans/topic-boxes-homepage.md`) work by construction, because the
intersection was decided at ingest.

## Risks

- **Thin lanes.** Sovereign AI is ~23 keyword hits across the entire corpus,
  Robotics 22. At current RSS volume a lane could sit empty for a week. Either
  accept staleness, merge Sovereign into Open Weights, or add feeds that
  actually cover it before shipping the lane.
- **A dropped article is gone.** Today a mis-scored article still lands in
  `/feed`. Here, no topic = never stored. Recall at gate 1 is the whole
  safety margin; keep the drop reason in `scored_url` so it can be audited
  and replayed.
- **Definition drift.** Retuning a topic description changes what gets
  ingested *going forward only* — the back catalogue was filtered under the
  old definition. Version the definitions and note the cutover.
- **Prototype quality depends on exemplars.** 5-10 hand-picked articles per
  topic is real editorial work, ~150 picks total. It is also the highest-
  leverage work in the plan.
- **RSS-only ceiling.** 60 feed publishers, ~60 genuinely new articles per
  run, spread over 17 topics. That's ~3-4 per topic per run *before*
  filtering. Precision is affordable; a 17th lane may not be.
