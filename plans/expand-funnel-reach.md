# Expand funnel reach

Code is on `claude/expand-cloud-agent-pipeline-2z5tgi`. The SQL below is **not
run** — it is for a human to apply against prod, in the order given.

## What shipped in code

- `Publisher.topic_gated` + migration `e3f4a5b6c7d8`. Internal only —
  `PublisherPublic` is unchanged, so no client regeneration.
- `drop_off_topic` in `pipeline/steps/fetch.py`, wired into `run.py` right after
  publisher resolution. A gated publisher's item must match the AI keyword
  pattern on its title or it is dropped — before any DB lookup, DNS, embedding
  or LLM call.
- `HN_AI_KEYWORDS` moved to `pipeline/heuristics.py` as `AI_TITLE_KEYWORDS`
  (two callers now; the `HN_` prefix no longer described it).
- Lab Watch is back in `build_sources`. It was disabled because thin
  search-snippet items reached the scorer; `_with_content` already re-fetches
  and drops those, which is what makes HN safe, so Lab Watch runs through the
  same path.
- Hacker News polls `newstories` alongside `topstories`, deduped by id and URL.
- New `pipeline/sources/reddit.py`: r/LocalLLaMA + r/MachineLearning `top/day`,
  public listing JSON, no key. The subreddit is the topic gate; posts are
  filtered on score, recency and having text to extract.
- `SourceStats.filtered_off_topic` so the funnel still accounts for every drop.
- `publishertype` gains `reddit` (migration `f4a5b6c7d8e9`) *and* a matching
  `PublisherType.reddit` member. Both halves are needed: the Postgres label
  alone would let the row insert and then break every read — SQLAlchemy raises
  `LookupError` for a label the StrEnum lacks, and `_active_publisher_links`
  selects all active publishers, so one such row takes the run down.
  `tests/test_models_enums.py` now fails if a migration adds an enum label
  Python does not have. `PublisherPublic` does not expose `type`, so the
  generated client is still unchanged.

## Order of operations

1. Deploy the branch (both migrations must be applied before step 2 — the SQL
   sets `topic_gated` and uses the `reddit` enum value).
2. Run the insert SQL.
3. First live run. Lab Watch costs one Tavily search per target per night;
   the target count goes from 5 to 19 with the inserts below.

Deploy order is already safe: `deploy-production.yml` runs `prestart.sh`
(`alembic upgrade head`) before `systemctl restart agentique-backend`, so the
`topic_gated` column exists before any code that selects it starts.

Verified end-to-end on a local restore of prod (prod head is `c1d2e3f4a5b6`,
exactly this chain's `down_revision`): both migrations apply, the SQL inserts
69 rows, a second run inserts 0, all 149 publishers load through the ORM, and
`build_sources` sees 120 feed publishers, 19 Lab Watch targets and 11 gated
publishers.

## 1. Zero-yield publishers

30 days to 2026-08-31: 24 publishers fetched more than 15 items and inserted
nothing. Together they account for ~840 fetches.

| publisher | fetched | inserted |
|---|---|---|
| The AI Architect | 116 | 0 |
| AI in public | 77 | 0 |
| Google AI Blog | 61 | 0 |
| Prompt-Led Product | 59 | 0 |
| AI Hero | 52 | 0 |
| Matt Paige | 48 | 0 |
| Department of Product | 47 | 0 |
| ToxSec - AI and Cybersecurity | 46 | 0 |
| Vik's Newsletter | 45 | 0 |
| Limited Edition Jonathan | 37 | 0 |
| Standout Systems by Teodora | 32 | 0 |
| Gradient Flow | 27 | 0 |
| Import AI | 27 | 0 |
| Artificial Code | 27 | 0 |
| Simon Willison's Newsletter | 26 | 0 |
| Senior Data Science Lead | 24 | 0 |
| Elevate by Addy Osmani | 23 | 0 |
| Purposeful AI | 23 | 0 |
| Digital Thoughts | 21 | 0 |
| Artificial Corner | 21 | 0 |
| AI by Aakash | 20 | 0 |
| AI Superhero | 20 | 0 |
| Understanding AI | 19 | 0 |
| Design with AI | 19 | 0 |

Three of these are worth a look before you cut them — the feed is alive and
fetching fine, so zero inserts is a scoring or dedup outcome rather than a dead
source. Whether that makes them worth carrying is your call, not mine:

- **Google AI Blog** (61 fetched) — first-party Google feed. Likely losing every
  item to dedup against Google DeepMind Blog, which covers the same posts.
- **Import AI**, **Simon Willison's Newsletter** — both still publish; both
  score below threshold consistently.

Deactivate list — strike whichever rows you want to keep, then run:

```sql
update publisher set is_active = false
where slug in (
  'the-ai-architect',
  'ai-in-public',
  'google-ai-blog',
  'prompt-led-product-for-pms-building-in-the-ai-era',
  'ai-hero',
  'matt-paige',
  'department-of-product',
  'toxsec-ai-and-cybersecurity',
  'vik-s-newsletter',
  'limited-edition-jonathan',
  'standout-systems-by-teodora',
  'gradient-flow',
  'import-ai',
  'artificial-code',
  'simon-willisons-newsletter',
  'senior-data-science-lead',
  'elevate-by-addy-osmani',
  'purposeful-ai',
  'digital-thoughts',
  'artificial-corner',
  'ai-by-aakash',
  'ai-superhero',
  'understanding-ai',
  'design-with-ai'
);
```

## 2. New publishers

69 rows: 43 plain RSS, 11 topic-gated RSS, 14 Lab Watch search targets, and the
Reddit row the new source resolves against. Every slug was checked against the
83 rows already in prod — no collisions. Guarded by `NOT EXISTS` rather than
`ON CONFLICT` (`publisher.slug` has no unique constraint), so re-running after a
partial apply inserts only what is missing. Validated against a local restore:
69 rows in, second run inserts 0.

The feed list came from the brief already probed; HTTP 200 is not editorial fit,
so treat this as a proposal — drop any row you do not want to carry.

See `plans/expand-funnel-reach.sql`.
