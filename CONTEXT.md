# Context

Glossary for words the code uses. If a term below and the code disagree, the
code wins — file a fix.

**Publisher** — the outlet an article came from (a blog, a lab's news page, a
subreddit). Not the same as a *source* (see below): one publisher can be
reached through more than one source, and `Publisher.type` records the one
the pipeline actually used.

**Publisher kind vs type** — two different axes on `Publisher`, easy to
confuse because both are enums on the same model:

- `kind` (`PublisherKind`) is *what the publisher is*: `individual`,
  `company`, `community`, `media`. Shown to readers.
- `type` (`PublisherType`) is *how the pipeline finds its articles*: `rss`,
  `substack`, `search`, `hn`, `reddit`, `email`, `ainews`, `other`. Internal
  ingestion detail, not exposed on the public API shapes.

**Source** — one of the pipeline's fetch adapters (`pipeline/sources/*.py`):
Hacker News, an AI-news aggregator, a curated Substack list, GitHub stars,
Reddit, a lab-watch crawler, email ingestion. A source yields raw items for
one or more publishers; it is a pipeline concept, not a database column.

**Trust** (`Publisher.trust`, `TrustLevel`) — `low` / `medium` / `high`,
hand-set per publisher. Used to weight or gate pipeline decisions; not shown
on the public API.

**Topic-gated** (`Publisher.topic_gated`) — a publisher flagged as posting
mostly off-topic content (a general engineering blog, not an AI one). When
set, the fetch step drops anything whose title misses the AI keyword list
before it costs an embedding or an LLM call. Ingestion policy, not part of
the public read API.

**Score** (`Article.score`) — an LLM's 1-100 rating of how actionable the
article is for a developer building with AI right now. The main noise
filter: only articles at or above the configured threshold get inserted at
all.

**Traction** — a story's outside signal that other people found it worth
reading, independent of the pipeline's own score: Hacker News points/comments
past a minimum, or a GitHub repo's star count. The traction gate holds back
low-traction submissions from the "everyone can post" sources so a repo its
author uploaded yesterday doesn't rank next to a release half the field
depends on. A publisher on `FIRST_PARTY_HOSTS` skips the gate — a lab's own
announcement is real news at zero votes.

**Run** (`PipelineRun`) — one row per nightly pipeline execution: start/end
time, duration, ok/fail, and per-source and per-publisher funnel counts
(fetched, filtered, inserted, errored). The record a human or a verifier
reads to see what last night's run actually did.
