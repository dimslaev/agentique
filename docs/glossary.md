# Glossary

Glossary for words the code uses. If a term below and the code disagree, the code wins - file a fix.

- **Publisher** - the outlet an article came from (a blog, a lab's news page, a subreddit). Different from a *source* (below): one publisher can be reached through more than one source. `Publisher.type` records the source actually used. An article is credited to the publisher whose site its URL is on when one is known, even when an aggregator found it; the item's `source` still names the aggregator.

- **Publisher kind vs type** - two enums on the same model, easy to confuse.
  - `kind` (`PublisherKind`) - what the publisher is: `individual`, `company`, `community`, `media`. Shown to readers.
  - `type` (`PublisherType`) - how the pipeline finds its articles: `rss`, `substack`, `search`, `hn`, `reddit`, `email`, `ainews`, `other`. Internal ingestion detail, not on the public API.

- **Source** - one of the pipeline's fetch adapters (`pipeline/sources/*.py`): Hacker News, an AI-news aggregator, a curated Substack list, GitHub stars, Reddit, a lab-watch crawler, email ingestion. A source yields raw items for one or more publishers. Pipeline concept, not a database column.

- **Trust** (`Publisher.trust`, `TrustLevel`) - `low` / `medium` / `high`, hand-set per publisher. Weights or gates pipeline decisions. A high-trust `individual` publisher's articles pass at 55 instead of 65 (`threshold_for` in `pipeline/steps/score.py`). Not on the public API.

- **Topic-gated** (`Publisher.topic_gated`) - a publisher flagged as mostly off-topic (a general engineering blog, not an AI one). When set, the fetch step drops anything whose title misses the AI keyword list before spending an embedding or LLM call on it. Ingestion policy, not part of the public read API.

- **Score** (`Article.score`) - an LLM's 1-100 rating of how actionable the article is for a developer building with AI right now. Main noise filter: only articles at or above the configured threshold get inserted. The scorer's one-sentence reason is kept in `Article.score_reason` (internal, not on the public API) and, for rejects, in `Reject.reason`.

- **Traction** - outside signal that people found a story worth reading, independent of the pipeline's own score: Hacker News points/comments past a minimum, or a GitHub repo's star count. Holds back low-traction submissions from the "everyone can post" sources. A first-party URL (`pipeline/first_party.py`) skips the gate - a lab's own announcement counts as news at zero votes.

- **Reject** (`Reject`, table `scored_url`) - a URL the funnel turned down, one row per URL. `stage` says which step dropped it (`thin_repo`, `prefilter`, `duplicate`, `below_threshold`, `unusable_summary`). It keeps what that step saw: title, source, publisher, the first 2000 chars of content, traction, score, and the scorer's `reason`. `filter_known_urls` reads it so a reject is never judged twice. Holds in a source (HN traction, recency) and a failed LLM call are deliberately not rejects: those come back next run. Rows from before 2026-09-13 carry only the URL.

- **Run** (`PipelineRun`) - one row per nightly pipeline execution: start/end time, duration, ok/fail, per-source and per-publisher funnel counts (fetched, filtered, inserted, errored). What a human or a verifier reads to see what last night's run did.

- **RawItem / Candidate / Scored / Persisted** (`pipeline/types.py`) - the four shapes an article takes going down the funnel, one per stage.
  - **RawItem** - what a source adapter emitted. Title, url, content, date, source name. Nothing else known yet.
  - **Candidate** - a raw item resolved to its Publisher: carries `publisher_id`, `trust`, `topic_gated`. Worth spending filter, embedding, LLM budget on.
  - **Scored** - a candidate the LLM rated at or above the threshold. Only survivors reach this stage.
  - **Persisted** - a scored article now stored as an `Article` row: has an `id`, sanitized title and content.
  - Each stage extends the one before, so a step's signature says where in the funnel it belongs. Enrichment narrows a `Persisted` to a `ProcessedArticle`: just the fields the embedding text is built from.
