# 20. Signed-in users reach the archive over MCP

## Status

Accepted.

## Context

The MCP server had two callers, both ours: a read token for questions about the
feed and a write token for the curation, newsletter and stories agents.
Developers with an account wanted their own agents to search the archive and
query it. The read token could not be handed out. Its `sql_query` reads the
internal tables, and `web_fetch` and `web_search` spend our keys.

## Decision

    account -> POST /users/me/mcp-token -> agq_... (shown once, hash stored)
    /mcp    -> shared tokens first, then the hash lookup -> scope `user`
    `user`  -> search, tags, sql_query over public_api. Nothing else.

- **One endpoint, three scopes.** `SharedSecret` gives a personal token the
  `user` scope. No OAuth: a token in a header is what MCP clients already take.
- **One token per account.** Stored as a SHA-256 hash, no expiry. Creating a new
  one replaces the old. Free for every signed-in user.
- **The `user` scope is an allowlist.** `USER_TOOLS` in `auth.py` names what it
  reaches. A server-wide middleware hides every other tool from its list and
  refuses a call to one, so a new tool is closed to users until someone names
  it.
- **Public SQL reads views through its own role.** Schema `public_api` holds
  `article`, `publisher`, `tag` and `article_tag` with the columns the site
  already shows. Role `mcp_public` has SELECT on that schema only, a 3 second
  statement timeout and 5 connections. Under the `user` scope `sql_query` logs
  in as that role, and refuses to run if the role can read `public.article`.
- **Article text is searched and never returned.** `search` reads the full text
  and returns a link and an excerpt of about 300 characters. The views have no
  `content` column.
- **Calls are limited per account.** 20 a minute and 500 a day, counted in the
  backend process.

## Consequences

- The views are created by a migration and the role by
  `deploy/sql-roles-public.sql`, run by hand on the box, so no password lands
  in git. Until the role exists a user's `sql_query` fails to connect. `search`
  and `tags` work without it.
- The backend runs 2 workers and each keeps its own count, so a user can make
  up to twice the limit. Move the count to Postgres if that matters.
- A column added to a table stays private until a migration adds it to a view.
- `sql_query` has one description for both callers, so users read one line
  about the internal tables they cannot reach.
- Users, likes by user, the ledger, runs, stories, analytics and the newsletter
  are not in the views.
