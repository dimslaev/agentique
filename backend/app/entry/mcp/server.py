"""The MCP server: the instance, its instructions, its tool list, and the ASGI app `main` mounts."""

from __future__ import annotations

from fastmcp import FastMCP

from app.entry.mcp.approve import approve
from app.entry.mcp.auth import SharedSecret, user_scope_gate
from app.entry.mcp.check_link import check_link
from app.entry.mcp.close_story import close_story
from app.entry.mcp.draft_issue import draft_issue
from app.entry.mcp.get_content import get_content
from app.entry.mcp.list_candidates import list_candidates
from app.entry.mcp.rate_limit import UserRateLimit
from app.entry.mcp.reject import reject
from app.entry.mcp.reject_many import reject_many
from app.entry.mcp.related import related
from app.entry.mcp.save_story import save_story
from app.entry.mcp.search import search
from app.entry.mcp.similar import similar
from app.entry.mcp.sql_query import sql_query
from app.entry.mcp.stories import stories
from app.entry.mcp.story_candidates import story_candidates
from app.entry.mcp.tags import tags
from app.entry.mcp.vocabulary import vocabulary
from app.entry.mcp.web_fetch import web_fetch
from app.entry.mcp.web_search import web_search
from app.entry.mcp.week import week

mcp = FastMCP(
    name="agentique",
    # Every caller reads this, a reader's own agent included, so it names
    # only the tools a personal token reaches. The pipeline's agents learn
    # theirs from each tool's description and from their skills.
    instructions=(
        "agentique is a curated archive of articles for people building with "
        "AI. `tags` lists the topics with article counts, `search` finds "
        "articles by keyword and by meaning, and `sql_query` runs read-only "
        "SQL over the archive. Start with `tags`, then pass slugs to `search`."
    ),
    auth=SharedSecret(),
    # The limit is outermost, so a call the gate refuses is counted too.
    middleware=[UserRateLimit(), user_scope_gate],
    tools=[
        search,
        tags,
        sql_query,
        web_fetch,
        web_search,
        list_candidates,
        get_content,
        similar,
        stories,
        check_link,
        vocabulary,
        approve,
        reject,
        reject_many,
        week,
        related,
        draft_issue,
        story_candidates,
        save_story,
        close_story,
    ],
)

# Mounted at /mcp by `app.main`, so the route inside this app is the bare root.
# Its lifespan starts the streamable-HTTP session manager and has to be handed
# to the parent app -- a mounted ASGI app never gets a lifespan of its own.
# Stateless: the backend runs several workers and a session lives in one
# worker's memory, so a client's next request would get a 404 from another.
mcp_app = mcp.http_app(path="/", stateless_http=True)
