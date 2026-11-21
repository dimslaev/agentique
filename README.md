# agentique

A curated feed of articles for people building with AI. A nightly pipeline collects candidates; a Claude Code session reads them and decides what gets published.

## Pipeline

Runs daily at 04:00. Collects, judges nothing.

- Fetch new items from feeds, newsletters, Hacker News and lab sites
- Follow tweets and redirect links to the real page
- Drop event, glossary and docs pages
- Fill in the full text; drop items with too little to read
- Drop URLs already published, rejected or waiting
- Credit each item to the site it is on, not where it was found
- Queue the rest as pending candidates

```mermaid
flowchart TD
    A[Feeds, newsletters, HN, lab sites] --> B[Fetch new items]
    B --> C[Tweets and redirects -> real page]
    C --> D{Event, glossary or docs page?}
    D -- yes --> X[Dropped]
    D -- no --> F[Fetch full text]
    F --> G{Enough to read?}
    G -- no --> X
    G -- yes --> E{Seen this URL before?}
    E -- yes --> X
    E -- no --> H[Credit to the site's publisher]
    H --> Q[Pending candidate]
```

## Curation

A Claude Code session after the pipeline. Decides every candidate.

- Reject the clear misses on title alone: off topic, funding, vendor product posts, digests
- Group copies of one story; reject the ones the feed already carries
- Read the rest and check the evidence: repo, model weights, paper, who wrote it
- Score 1-100 on evidence and reach
- Approve: publish with summary and tags; or reject with a reason
- Every verdict is kept, so no URL is judged twice

```mermaid
flowchart TD
    D[Pending candidate] --> E[Claude curation session]
    E --> F{Pre-filter on title}
    F -- clearly off --> R[Reject + reason]
    F -- maybe --> G[Group duplicates]
    G -- feed already has it --> R
    G -- new story --> H[Read the article]
    H --> I[Check evidence: repo, weights, paper, who wrote it]
    I --> J[Score 1-100]
    J -- below the bar --> R
    J -- good enough --> P[Approve: publish with summary + tags]

    P --> M[Daily mail, newsletter, stories]
    R --> L[(Past decisions: never judged again)]
    P --> S[Discover: feeds that earn approvals stay on]
    R --> S
```

## Discover publishers

A daily Claude Code session. Decides which sites the pipeline polls; publishes nothing.

- Hacker News and newsletters surface new sites; each becomes an inactive publisher
- Turn off polled feeds that stopped earning approvals: none in 10+ decisions, under 5% over 30+, or silent for 120 days (aggregators are never deactivated)
- Probe inactive publishers that have earned an approval: find their feed, check it is their own posts and still alive
- Read their recent posts and judge each against the curation rubric (passes at 70+)
- Activate at 3+ passes and a 40%+ pass rate; otherwise switch off with the reason
- No feed: a lab or company is searched on its own site instead; anyone else stays off

```mermaid
flowchart TD
    N[New site seen via HN or a newsletter] --> I[Inactive publisher]
    I --> P{Earned an approval?}
    P -- no --> W[Stays inactive]
    P -- yes --> F{Feed found, own posts, alive?}
    F -- no feed, lab or company --> S[Search its site]
    F -- no --> OFF[Switched off + reason]
    F -- yes --> R[Read recent posts against the rubric]
    S --> R
    R --> T{3+ passes and 40%+?}
    T -- yes --> ON[Activated: pipeline polls it]
    T -- no --> OFF

    ON --> C{Still earning approvals?}
    C -- no --> OFF
    C -- yes --> ON
```

## Search

- One query box matches by keyword: Postgres full-text over title, summary, body and tag names, so an exact name like "vLLM" matches
- Filters (tags, kinds, publisher, date) narrow the articles before ranking

## Newsletter

- Signing up takes only an email: it makes the account, adds the address to the Resend audience, and mails a sign-in link (no passwords)
- Every Friday a Claude Code session drafts the issue: 10-12 of the week's most useful articles, liked ones first, in 3-4 sections with a one-line summary each
- The same file is the email and a blog post in `frontend/content/blog/`
- It lands as a Resend draft; a person sends it

## API and MCP

- The article endpoints (list, search, facets, publishers, tags, stats) are public: no account, no rate limit, no date window
- A token is optional and only fills in `liked_by_me`
- An MCP server at `/mcp` gives coding agents `search_articles`, `list_tags` and read-only `sql_query` over the archive
- A signed-in reader makes an MCP token at `/connect-mcp` and copies the config for Claude Code, OpenCode, Cursor, Codex CLI or VS Code

## Stack

- PostgreSQL + pgvector - the only Docker container (`docker compose up -d`)
- FastAPI backend, REST API and MCP server - native via uv, systemd in production
- Pipeline - native via uv, systemd timer
- React + Vite + Tailwind frontend - static files served by Caddy
- model2vec - embeddings for spotting the same story across publishers

## Docs

- [Backend](./docs/backend.md)
- [Frontend](./docs/frontend.md)
- [Glossary](./docs/glossary.md)
- [Deployment](./deploy/README.md)
