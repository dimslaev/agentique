# Agentique — what this project is

Agentique (agentique.ch) is an AI news feed for people building with AI: developers,
founders, and tech leads who want the signal without wading through hype. Instead of
scrolling ten newsletters and three subreddits, you get one feed of articles that have
already been filtered down to seven subjects the site actually covers
— and you can semantically search across all of it.

Think of it as an automated editorial desk: a robot intern that reads everything on the
internet about AI every night, throws out everything that is not on the beat, and hands
you a short digest by morning. Most of what it reads does not make it in.

## What it does today

**A public landing page (`/`).** Anyone gets a hardcoded "top selection" of articles —
one box per source (a few model labs, a newsletters box aggregating Ben's Bites/TLDR/
The Batch/etc.) — plus the newsletter signup and a link to create an account. It's a
static marketing page, not backed by the live article API; a separate agent keeps its
source data current.

**A filtered article feed (`/feed`, public — no account needed).** Lists recent articles
newest-first (or by popularity). Each entry shows a short excerpt of the article, its
categories, and a "kind" (repo, paper, model, blog, product, announcement). You can
filter by category, kind, publisher, and time window (last 3 days / week / month).

The seven categories are the whole editorial policy: AI Labs, Model Releases, Open
Weights, Coding Agents, Tool Use & MCP, Local AI, and Inference & Optimization. An
article that matches none of them is not stored at all — so unlike a tag, a category is
not a label added after the fact, it is the reason the article is in the database.

**Semantic search.** Typing a query searches by meaning, not keyword — it embeds your
query and finds the nearest articles in vector space, so "how do I run a model locally"
surfaces relevant pieces even if none of them use that exact phrase.

**Newsletter signup.** Visitors can subscribe with just an email from the landing page;
subscribers are synced to a Resend audience for future digest emails (the sending side
isn't built yet — this is capture only, for now). Separate from creating an account —
subscribing doesn't create a login, and signing up for an account doesn't subscribe you.

**A developer API — public, paid tier not live yet.** The article endpoints (list,
search, facets, publishers, categories, stats) are open and unauthenticated, with no date
window or rate limit; a token is optional and only fills in `liked_by_me`. Liking an
article and the profile page are the only things that need an account. The
`/developers` page still pitches a $10/mo Pro tier for programmatic access — the
upgrade button fires an analytics event and shows a "coming soon" dialog; no real
Stripe integration exists yet.

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
4. **Match against the categories** — two cheap local checks first (a distilled
   keep/drop classifier, then a similarity check against each category), and then an
   LLM is asked which of the seven categories the article belongs to. Matching none is
   a normal, common answer, and an article that matches none is never stored. This is
   the main noise filter, and it replaced an older 1–100 relevance score: "how good is
   this?" let through articles that belonged nowhere on the site.
5. **Insert & clean up the title** — the article is saved, then a second LLM pass
   tightens up clickbait-y or vague titles into something plain and informative.
6. **Pull the full article text** — for sources that only gave us a link, the pipeline
   fetches and extracts the actual article body (skipping paywalled junk, ads, nav).
7. **Excerpt** — the card text is a sanitized slice of the article's own opening:
   markup, entities, emoji and README banner art stripped, trimmed on a word
   boundary. No LLM. This used to be an LLM summary; it was the pipeline's most
   reliable source of garbled text, and an excerpt cannot invent anything the
   source did not say.
8. **Embed** — a small, fast local embedding model turns the title + excerpt into a
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
  the fetch → filter → match → excerpt → embed work described above.
- **Embeddings**: model2vec — a tiny, fast, CPU-only static embedding model, no GPU or
  external API call needed for search.
- **Frontend**: React + Vite + Tailwind, talking to the backend through a generated
  TypeScript client.
- **Deploy**: a single VPS — the db in Docker, backend and pipeline as systemd
  services, the frontend as static files behind Caddy.

The whole thing is a fork of a well-known open-source FastAPI starter template, so a lot
of the plumbing (auth scaffolding, migrations, project layout, CI) is inherited rather
than built from scratch — Agentique-specific logic lives in a small number of clearly
separate files rather than scattered through upstream code, which keeps it easy to pull
in upstream improvements later.

## Where things stand / what's next

The product today is deliberately narrow: a public landing page, a public feed and
search, one capture-only newsletter form. Things explicitly not
built yet (and worth knowing about if you're picking up work here): sending the actual
newsletter digest, a real Pro API with keys and billing (currently a "coming soon"
button), saved articles / personalization, an MCP server so AI agents can query the
feed directly, the Substack discovery crawler and email-newsletter ingestion mentioned
above, and a real load/scale test (current data volume is small — this has been an
architecture spike more than a performance one so far).

If you want the ground-level detail — endpoints, models, exact commands — see
`backend/README.md`, `frontend/README.md`, and `development.md`. `CHANGES.md` tracks
every place this fork has diverged from the upstream template, which is the fastest way
to see what's actually Agentique-specific versus inherited scaffolding.
