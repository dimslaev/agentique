# Agentique — what this project is

Agentique (agentique.ch) is an AI news feed for people building with AI: developers,
founders, and tech leads who want the signal without wading through hype. Instead of
scrolling ten newsletters and three subreddits, you get one feed of articles that have
already been filtered, scored, summarized, and tagged — and you can semantically search
across all of it.

Think of it as an automated editorial desk: a robot intern that reads everything on the
internet about AI every night, throws out the noise, and hands you a short, ranked
digest by morning.

## What it does today

**A filtered, ranked article feed.** The homepage lists recent articles sorted by an
LLM-assigned "developer-actionability" score (or by recency). Each entry shows a
2–3 line factual summary, a category (Models / Dev / Research), and a "kind" (repo,
paper, model, blog, product, announcement). You can filter by category, kind, score,
and time window (last 3 days / week / month).

**Semantic search.** Typing a query searches by meaning, not keyword — it embeds your
query and finds the nearest articles in vector space, so "how do I run a model locally"
surfaces relevant pieces even if none of them use that exact phrase.

**Newsletter signup.** Visitors can subscribe with an email + category preferences;
subscribers are synced to a Resend audience for future digest emails (the sending side
isn't built yet — this is capture only, for now).

**A public API.** Everything above is backed by a documented REST API (auto-generated
OpenAPI/Swagger) that anyone could build a client against — a Slack bot, a CLI, a
personal dashboard.

## How the pipeline works

Once a day, a scheduled job goes out, gathers candidate articles from a handful of
sources (Hacker News, an AI-news aggregator feed, and a curated list of Substack
newsletters), and runs each fresh batch through a chain of small, focused steps:

1. **Skip anything already seen** — URLs already in the database, or already evaluated
   and rejected before, are dropped immediately.
2. **Drop dead links** — a quick DNS check filters out URLs whose domains no longer
   resolve.
3. **Deduplicate by meaning** — an LLM compares new articles against everything
   published in the last two weeks and drops ones that are "the same story," even if
   the wording or source differs.
4. **Score for relevance** — an LLM rates each surviving article 1–100 on how
   actionable it is for a developer building with AI right now. Only the top scorers
   (currently ≥76) make it into the database at all — this is the main noise filter.
5. **Insert & clean up the title** — the article is saved, then a second LLM pass
   tightens up clickbait-y or vague titles into something plain and informative.
6. **Pull the full article text** — for sources that only gave us a link, the pipeline
   fetches and extracts the actual article body (skipping paywalled junk, ads, nav).
7. **Summarize & categorize** — another LLM pass turns the full text into the 2–3 line
   summary and assigns category + kind tags shown in the feed.
8. **Embed** — a small, fast local embedding model turns the title + summary into a
   vector, which is what powers semantic search.

All the LLM steps are defined declaratively as prompt functions (via BAML) rather than
hand-rolled prompt strings scattered through the code, so tweaking a prompt or swapping
a model is a config change, not a refactor.

There are a few more pipeline building blocks already defined (a Substack discovery
crawler that finds new AI-focused publications to follow, and newsletter-email
ingestion that extracts article links/products out of HTML emails) that exist but
aren't wired into the nightly run yet — candidates for whoever picks up sourcing next.

## Under the hood, briefly

- **Backend**: FastAPI (Python), auto-generates the OpenAPI spec the frontend client is
  built from.
- **Database**: Postgres with the pgvector extension — one table holds articles plus
  their embedding vectors, so relevance search is just a SQL query.
- **Pipeline**: a separate scheduled Python process (cron-style, once a day) that does
  the fetch → filter → score → summarize → embed work described above.
- **Embeddings**: model2vec — a tiny, fast, CPU-only static embedding model, no GPU or
  external API call needed for search.
- **Frontend**: React + Vite + Tailwind, talking to the backend through a generated
  TypeScript client.
- **Deploy**: Docker Compose on a single VPS — db, backend, pipeline, frontend, and an
  Adminer UI for poking at the database directly.

The whole thing is a fork of a well-known open-source FastAPI starter template, so a lot
of the plumbing (auth scaffolding, migrations, project layout, CI) is inherited rather
than built from scratch — Agentique-specific logic lives in a small number of clearly
separate files rather than scattered through upstream code, which keeps it easy to pull
in upstream improvements later.

## Where things stand / what's next

The product today is deliberately narrow: one public feed, one search endpoint, one
capture-only newsletter form, no user accounts. Things explicitly not built yet (and
worth knowing about if you're picking up work here): sending the actual newsletter
digest, user accounts / saved articles / personalization, an MCP server so AI agents can
query the feed directly, the Substack discovery crawler and email-newsletter ingestion
mentioned above, and a real load/scale test (current data volume is small — this has
been an architecture spike more than a performance one so far).

If you want the ground-level detail — endpoints, models, exact commands — see
`backend/README.md`, `frontend/README.md`, and `development.md`. `CHANGES.md` tracks
every place this fork has diverged from the upstream template, which is the fastest way
to see what's actually Agentique-specific versus inherited scaffolding.
