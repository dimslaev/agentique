# rss pipeline timeout fix

## Problem
LLM calls time out at summarize / categorize / assign-tags. Summarize does a
long generation per article; tags run in big batches. Content often thin, so
summarizer works from teasers.

## Changes

### Fetch
- Poll rss + substack + Hacker News. Drop Newsletter (IMAP), AI News, Lab Watch
  from `build_sources`. HN items start thin but the fetch step fills their
  content (and drops any it cannot), so they survive.
- Fill content at fetch time: for thin items (< `MIN_CONTENT_CHARS`) do direct
  fetch then residential-proxy fetch (`fetch_full_content`).
- Articles still empty after that: drop and log. Only content-bearing items go
  downstream.

### Enrich
- Content is always full now (fetch fills it), so `SummarizeAndCategorize`
  works from the real article, not a teaser: one call per article yields the
  summary, categories, and kind together.
- Summarize + assign tags per article with a delay between calls, not batches —
  a slow/failed call costs one article, not a whole batch.
- Drop the separate `extract_full_content` enrich step (moved to fetch).

### Persist
- Sanitize content on insert (title already sanitized).

### Read / frontend
- `to_public` sends `article.summary`; the frontend renders it (unchanged).
- Full sanitized content stays in the DB `content` column; article search
  matches `content` (fuller than summary).

## Client generation
- No BAML signature change (reused existing `SummarizeAndCategorize`), so the
  regenerated `baml_client/` matches the checked-in one.
- No OpenAPI schema change, so no frontend client regen needed.
