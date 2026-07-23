# RSS pipeline rewrite (`pipeline_new`)

Self-contained rewrite of the ingestion pipeline, scoped to RSS + substack only.
Imports nothing from `pipeline.*`. Reuses only the generated `baml_client` and
the schema in `app.models`. The old pipeline (HN, AI News, IMAP, lab-watch,
Tavily) will be deleted once this replaces it.

## Why

Old pipeline was built for many source types and carried their failure modes into
RSS handling. Goal: fewer moving parts, fewer LLM calls, less bad data.

## One object, not a chain of dicts

`PipelineArticle` (a dataclass) carries an article from fetched to processed. Every
field has a safe default, so a partially-processed article is always valid — no
stringly-typed dict access, no missing-key surprises.

## Flow

```
fetch -> filter_known -> dedup -> score -> persist -> enrich
```

- **fetch** — poll every active RSS/substack publisher in parallel. Each feed
  tried direct first, retried through the residential proxy only on 403/429.
  Feed body (`content:encoded`) extracted + sanitized to plain text. Within-run
  URL dedup. Publisher id/name/trust stamped from the DB row we polled — no
  resolve-by-name, no unknown-source quarantine.
- **filter_known** — drop URLs already an Article or a rejected ScoredUrl.
- **dedup** — embedding cosine shortlist, then one LLM check against the last 14
  days. Non-fatal: a dedup crash keeps everything rather than dropping the batch.
- **score** — cheap keep/drop classifier trims obvious junk, then the LLM scorer
  (batches of 5). Rejects recorded in ScoredUrl so they aren't re-fetched.
- **persist** — insert what cleared the score threshold (76).
- **enrich** — summary + categories + kind (per article, isolated), tags
  (batched, validated against the DB vocabulary), embedding.

## Reliability decisions (vs old pipeline)

- **No title rewriting.** RSS/substack titles are editorial and clean — the old
  `ImproveTitles` LLM call existed for HN-style stubs and was a top source of
  corrupted titles (markdown, CJK, JSON leakage). Titles are now sanitized, not
  regenerated. One fewer LLM call per article, one whole class of bad data gone.
- **Enrich only when necessary.** Feeds already carry the full body, so the
  network is re-touched only for an entry whose body is a teaser (< 500 chars),
  and only through the metered proxy as a fallback.
- **Always sanitized.** Feed bodies go through the same trafilatura + blocker
  pass as fetched pages. Every LLM field is sanitized and gated before it is
  stored — a corrupted summary is dropped (no fallback), a bad title falls back
  to the feed's own.
- **Timeouts.** Reuses the BAML `Nvidia` fallback chain (Gemini -> gpt-oss ->
  Ministral). Small batches, per-item isolation on enrichment, a rate-limit
  pause between batches. One article failing never sinks the rest.
- **Idempotent rejects.** Pre-filter drops and sub-threshold scores are recorded
  so a later run skips them.

## Reused BAML functions (no regeneration)

`ScoreArticles`, `SummarizeAndCategorize`, `CategorizeOnly`, `AssignTags`,
`SemanticDedup`. `ImproveTitles`, `ClassifyKind`, and the discover/extract
functions are intentionally not used.

## Files

`config, types, util, text, http, db, embedding, content, feeds, dedup, llm,
pipeline, run` under `backend/pipeline_new/`. Keep-drop weights copied to
`pipeline_new/keep_drop_model.npz`. Pure-function tests under
`backend/tests/pipeline_new/`.

## Not carried over yet

Health/anomaly reporting (`pipeline.health`) and the per-source stats funnel.
Add back against `pipeline_new` when the old pipeline is removed.
