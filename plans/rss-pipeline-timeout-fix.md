# rss pipeline timeout fix

## Problem
LLM calls time out at summarize / categorize / assign-tags. Summarize does a
long generation per article; tags run in big batches. Content often thin, so
summarizer works from teasers.

## Changes

### Fetch
- Only poll rss + substack. Drop Hacker News, Newsletter (IMAP), AI News, Lab
  Watch from `build_sources`.
- Fill content at fetch time: for thin items (< `MIN_CONTENT_CHARS`) do direct
  fetch then residential-proxy fetch (`fetch_full_content`).
- Articles still empty after that: drop and log. Only content-bearing items go
  downstream.

### Enrich
- No summarize. Content is always full now, so categorize straight from
  content via new BAML `CategorizeContent(title, content) -> categories, kind`
  (no summary generation = smaller output = no timeout).
- Categorize + assign tags per article with a delay between calls, not batches.
- Tags read the article content, not a summary.
- Drop the separate `extract_full_content` enrich step (moved to fetch).

### Persist
- Sanitize content on insert (title already sanitized).

### Read / frontend
- `to_public` sends a trimmed, sanitized content preview in the `summary`
  field. Frontend already renders that field, so it now shows trimmed content.
- Full content stays in the DB `content` column; `summary` column no longer
  populated by the pipeline.

## Client generation
- Regenerate `baml_client/` after the BAML change.
- No OpenAPI schema change (reused `summary` response field), so no frontend
  client regen needed.
