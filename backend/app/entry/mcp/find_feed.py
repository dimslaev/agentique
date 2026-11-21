"""The `find_feed` tool: a site's feed and its newest entries."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.entry.mcp.auth import require_write
from app.features.curation import service as curation


def find_feed(url: str) -> dict[str, object]:
    """Find the RSS or Atom feed for a site and list its newest 10 entries.

    Tries `url` itself, then the feeds the page declares, then /feed,
    /rss.xml, /atom.xml, /index.xml, /feed.xml and /rss. Returns `feed_url`
    and `entries`: `title`, `link`, `published` (date, or "" when the feed
    gives none) and `judged`: `approved`, a ledger stage such as
    `below_threshold` or `pending`, or "" when agentique has never seen it.
    `entries` is empty when the feed is real but lists nothing today, as
    arXiv's do at the weekend: probe it another day. Fails when no feed
    answers.
    """
    require_write()
    with Session(engine) as session:
        found = curation.find_feed(session, url)
    if found is None:
        raise ToolError(f"No feed found at {url}")
    return found
