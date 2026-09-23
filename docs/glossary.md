# Glossary

Glossary for words the code uses. If a term below and the code disagree, the code wins - file a fix.

- **Publisher** - the outlet an article came from (a blog, a lab's news page, a subreddit). Different from a *source* (below): one publisher can be reached through more than one source. `Publisher.type` records the source actually used. An article is credited to the publisher whose site its URL is on when one is known, even when an aggregator found it; the item's `source` still names the aggregator.

- **Publisher kind vs type** - two enums on the same model, easy to confuse.
  - `kind` (`PublisherKind`) - what the publisher is: `individual`, `company`, `community`, `media`. Shown to readers.
  - `type` (`PublisherType`) - how the pipeline finds its articles: `rss`, `substack`, `search`, `hn`, `reddit`, `email`, `ainews`, `other`. Internal ingestion detail, not on the public API.

- **Source** - one of the pipeline's fetch adapters (`pipeline/sources/*.py`): Hacker News, the RSS/Substack feeds, a lab-watch crawler, email newsletters. A source yields raw items for one or more publishers. Pipeline concept, not a database column.

- **Trust** (`Publisher.trust`, `TrustLevel`) - `low` / `medium` / `high`, hand-set per publisher. No longer read (ADR 11): the curation agent sees each publisher's approval rate instead (`approved` in `list_candidates`: approvals / decisions over 90 days, or "new"). The column stays. Not on the public API.

- **Topic-gated** (`Publisher.topic_gated`) - a publisher flagged as mostly off-topic (a general engineering blog, not an AI one). No longer read: the fetch step used to drop its off-topic titles, and the curation agent judges topic now (ADR 11). The column stays. Hacker News keeps its own title keyword gate (`is_on_topic` in `pipeline/sources/hn.py`).

- **Score** (`Article.score`) - a 1-100 rating of how actionable the article is for a developer building with AI right now. Written by the curation agent, which reads the page before it decides (see **Candidate** below and ADR 9); an LLM in the pipeline used to write it from a title and a 200-char snippet. The one-sentence reason is kept in `Article.score_reason` (internal, not on the public API) and, for rejects, in `Reject.reason`.

- **Candidate** - overloaded, and the two senses are one step apart.
  - The *type* `Candidate` (`pipeline/types.py`) - a raw item resolved to its Publisher, mid-funnel.
  - A *candidate* in the feed's sense - an article the nightly run has queued and the curation agent has not judged yet: a `Reject` row at stage `pending`. It becomes an `Article` on approval and a `below_threshold` reject otherwise. Until then it is not visible anywhere a reader can see.

- **Curation agent** - the Claude Code session that runs at 05:00, an hour after the pipeline, reads the pending candidates through the MCP tools (`list_candidates`, `get_content`, `similar`, `stories`, `check_link`, `approve`, `reject`, `reject_many`) and decides each one. Its rubric is `.claude/skills/curate/SKILL.md`. It is the only judge the feed has and the only thing that writes an `Article`.

- **Coverage** - how many distinct publishers carry one story, counted by `similar` and `stories` (`pipeline/curation.py`): rows within 0.30 cosine distance of each other across the feed and the ledger. Reach evidence for the curation agent, like traction.

- **Traction** - outside signal that people found a story worth reading, independent of the pipeline's own score: Hacker News points/comments past a minimum, or a GitHub repo's star count. Holds back low-traction submissions from the "everyone can post" sources. A first-party URL (`pipeline/first_party.py`) skips the gate - a lab's own announcement counts as news at zero votes.

- **Reject** (`Reject`, table `scored_url`) - a URL the funnel turned down, one row per URL. `stage` says which step dropped it - `below_threshold` for the agent's rejects; `thin_repo`, `prefilter`, `duplicate` and `unusable_summary` are on old rows only, from gates that are gone - or `pending`, the one stage that is not a rejection at all: a candidate still waiting on the agent. It keeps what that step saw: title, source, publisher, the first 2000 chars of content, traction, the repo / model / paper / docs `links` the article body makes, score, and the judge's `reason`. `filter_known_urls` reads it so a reject is never judged twice. Holds in a source (HN traction, recency) and a failed LLM call are deliberately not rejects: those come back next run. Rows from before 2026-09-13 carry only the URL.

- **Run** (`PipelineRun`) - one row per nightly pipeline execution: start/end time, duration, ok/fail, per-source and per-publisher funnel counts (fetched, filtered, inserted, errored). What a human or a verifier reads to see what last night's run did.

- **RawItem / Candidate / Scored / Persisted** (`pipeline/types.py`) - the four shapes an article takes going down the funnel, one per stage.
  - **RawItem** - what a source adapter emitted. Title, url, content, date, source name. Nothing else known yet.
  - **Candidate** - a raw item resolved to its Publisher: carries `publisher_id`.
  - **Scored** - a candidate the curation agent approved, with its score. The nightly run never produces one: it ends at a pending candidate, and `curation.approve` builds the shape from the row the agent judged.
  - **Persisted** - a scored article now stored as an `Article` row: has an `id`, sanitized title and content.
  - Each stage extends the one before, so a step's signature says where in the funnel it belongs. Enrichment narrows a `Persisted` to a `ProcessedArticle`: just the fields the embedding text is built from.
