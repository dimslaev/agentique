"""The MCP server: the instance, its instructions, its tool list, and the ASGI app `main` mounts."""

from __future__ import annotations

from fastmcp import FastMCP

from app.entry.mcp.activate_publisher import activate_publisher
from app.entry.mcp.approve_article import approve_article
from app.entry.mcp.auth import SharedSecret, scope_gate
from app.entry.mcp.check_repo import check_repo
from app.entry.mcp.close_story import close_story
from app.entry.mcp.deactivate_publisher import deactivate_publisher
from app.entry.mcp.draft_newsletter import draft_newsletter
from app.entry.mcp.find_duplicates import find_duplicates
from app.entry.mcp.find_feed import find_feed
from app.entry.mcp.find_similar import find_similar
from app.entry.mcp.get_last_week_articles import get_last_week_articles
from app.entry.mcp.list_candidates import list_candidates
from app.entry.mcp.list_labels import list_labels
from app.entry.mcp.list_tags import list_tags
from app.entry.mcp.rate_limit import UserRateLimit
from app.entry.mcp.read_article import read_article
from app.entry.mcp.reject_articles import reject_articles
from app.entry.mcp.review_publishers import review_publishers
from app.entry.mcp.save_story import save_story
from app.entry.mcp.search_articles import search_articles
from app.entry.mcp.sql_query import sql_query
from app.entry.mcp.web_fetch import web_fetch
from app.entry.mcp.web_search import web_search

mcp = FastMCP(
    name="agentique",
    # Every caller reads this, a reader's own agent included, so it names
    # only the tools a personal token reaches. The pipeline's agents learn
    # theirs from each tool's description and from their skills.
    instructions=(
        "agentique is a curated archive of articles for people building with "
        "AI. `list_tags` lists the topics with article counts, `search_articles` finds "
        "articles by keyword, and `sql_query` runs read-only "
        "SQL over the archive. Start with `list_tags`, then pass slugs to `search_articles`."
    ),
    auth=SharedSecret(),
    # The limit is outermost, so a call the gate refuses is counted too.
    middleware=[UserRateLimit(), scope_gate],
    tools=[
        search_articles,
        list_tags,
        sql_query,
        web_fetch,
        web_search,
        list_candidates,
        read_article,
        find_similar,
        find_duplicates,
        check_repo,
        list_labels,
        approve_article,
        reject_articles,
        get_last_week_articles,
        draft_newsletter,
        save_story,
        close_story,
        review_publishers,
        find_feed,
        activate_publisher,
        deactivate_publisher,
    ],
)

# Mounted at /mcp by `app.main`, so the route inside this app is the bare root.
# Its lifespan starts the streamable-HTTP session manager and has to be handed
# to the parent app -- a mounted ASGI app never gets a lifespan of its own.
# Stateless: the backend runs several workers and a session lives in one
# worker's memory, so a client's next request would get a 404 from another.
mcp_app = mcp.http_app(path="/", stateless_http=True)
