"""The MCP server: the instance, its instructions, its tool list, and the ASGI app `main` mounts."""

from __future__ import annotations

from fastmcp import FastMCP

from app.entry.mcp.approve import approve
from app.entry.mcp.auth import SharedSecret
from app.entry.mcp.check_link import check_link
from app.entry.mcp.close_story import close_story
from app.entry.mcp.draft_issue import draft_issue
from app.entry.mcp.get_content import get_content
from app.entry.mcp.list_candidates import list_candidates
from app.entry.mcp.reject import reject
from app.entry.mcp.reject_many import reject_many
from app.entry.mcp.related import related
from app.entry.mcp.save_story import save_story
from app.entry.mcp.similar import similar
from app.entry.mcp.sql_query import sql_query
from app.entry.mcp.stories import stories
from app.entry.mcp.story_candidates import story_candidates
from app.entry.mcp.vocabulary import vocabulary
from app.entry.mcp.web_fetch import web_fetch
from app.entry.mcp.web_search import web_search
from app.entry.mcp.week import week

mcp = FastMCP(
    name="agentique",
    instructions=(
        "Tools for the agentique article pipeline. Reading: `sql_query` reads "
        "the Postgres database (publishers, articles, scores, pipeline runs), "
        "`web_fetch` reads one page, `web_search` finds pages. Curation, with "
        "the write token only: `list_candidates` lists what is waiting on a "
        "verdict, `get_content` pages through the stored text for one of them, "
        "`similar` and `stories` compare candidates with the feed, "
        "`check_link` looks up a repo or model, `vocabulary` lists the labels, "
        "and `approve`, `reject` and `reject_many` settle them. Weekly "
        "newsletter, with the write token only: `week` ranks the week's "
        "topics, `related` finds what else covers one, and `draft_issue` "
        "drafts an issue for a person to send and says where to save it as a "
        "blog post. Stories, with the write token only: `story_candidates` "
        "lists open stories and unassigned clusters, `save_story` creates or "
        "extends one, `close_story` closes one."
    ),
    auth=SharedSecret(),
    tools=[
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
mcp_app = mcp.http_app(path="/")
