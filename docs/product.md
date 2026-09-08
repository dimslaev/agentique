# Agentique — what this project is

Agentique (agentique.ch) is an AI news feed for people building with AI: developers,
founders, and tech leads who want the signal without wading through hype. Instead of
scrolling ten newsletters and three subreddits, you get one feed of articles that have
already been filtered, scored, categorized, and tagged — and you can semantically search
across all of it.

Think of it as an automated editorial desk: a robot intern that reads everything on the
internet about AI every night, throws out the noise, and hands you a short, ranked
digest by morning.

## What it does today

**A public landing page (`/`).** Anyone gets a hardcoded "top selection" of articles —
one box per source (a few model labs, a newsletters box aggregating Ben's Bites/TLDR/
The Batch/etc.) — plus the newsletter signup and a link to create an account. It's a
static marketing page, not backed by the live article API; a separate agent keeps its
source data current.

**A filtered, ranked article feed (`/feed`, public — no account needed).** Lists recent
articles sorted by an LLM-assigned "developer-actionability" score (or by recency).
Each entry shows a category (Models / Dev / Research) and a "kind" (repo, paper, model,
blog, product, announcement). You can filter by category, kind, score, and time window
(last 3 days / week / month).

**Semantic search.** Typing a query searches by meaning, not keyword — it embeds your
query and finds the nearest articles in vector space, so "how do I run a model locally"
surfaces relevant pieces even if none of them use that exact phrase.

**Newsletter signup.** Visitors can subscribe with just an email from the landing page;
subscribers are synced to a Resend audience for future digest emails (the sending side
isn't built yet — this is capture only, for now). Separate from creating an account —
subscribing doesn't create a login, and signing up for an account doesn't subscribe you.

**A developer API — public, paid tier not live yet.** The article endpoints (list,
search, facets, publishers, tags, stats) are open and unauthenticated, with no date
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
3. **Ask whether anyone else thought it was news** — an aggregator hands us every
   submission, not an edited selection, so a repo its author uploaded yesterday
   arrives looking exactly like a release half the field depends on. Two outside
   signals separate them: on Hacker News, the story's own points and comments (a
   post nobody read is held back rather than published, and re-checked the next
   day once the votes have settled); for anything linking to a GitHub repo, the
   repo's star count. A lab publishing on its own domain skips both — that is
   news at zero votes.
4. **Score for relevance** — an LLM rates each surviving article 1–100 on how
   actionable it is for a developer building with AI right now. Only the top scorers
   (currently ≥76) make it into the database at all — this is the main noise filter.
5. **Insert & clean up the title** — the article is saved, then a second LLM pass
   tightens up clickbait-y or vague titles into something plain and informative.
6. **Pull the full article text** — for sources that only gave us a link, the pipeline
   fetches and extracts the actual article body (skipping paywalled junk, ads, nav).
7. **Categorize & tag** — another LLM pass assigns category + kind and 1-3 tags from a
   controlled vocabulary, shown in the feed.
8. **Embed** — a small, fast local embedding model turns the title + a content snippet
   into a vector, which is what powers semantic search.

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
  the fetch → filter → score → categorize → embed work described above.
- **Embeddings**: model2vec — a tiny, fast, CPU-only static embedding model, no GPU or
  external API call needed for search.
- **Frontend**: React + Vite + Tailwind, talking to the backend through a generated
  TypeScript client.
- **Deploy**: a single VPS — the db in Docker, backend and pipeline as systemd
  services, the frontend as static files behind Caddy.


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
`backend/README.md` and `frontend/README.md`.
