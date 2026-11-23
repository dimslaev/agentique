"""The `add_publisher` tool: make the publisher a URL belongs to."""

from __future__ import annotations

from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.engine import engine
from app.core.logging import log
from app.features.collect import service as collect
from app.features.collect.model import QueueError


def add_publisher(url: str, reason: str) -> str:
    """Make the publisher a URL belongs to, as the nightly run would.

    A site we do not carry gets an inactive publisher with only a `website`
    link and the kind `unknown`; the nightly run does not poll it. A site we
    already carry returns its publisher unchanged. Probe it with `find_feed`
    and switch it on with `activate_publisher`. `reason` says why it is worth
    a look, e.g. "AINews top story 2026-11-20"; it goes to the log, since the
    publisher has no column for it.
    """
    if not reason.strip():
        raise ToolError("Give the reason, naming the competitor")
    with Session(engine) as session:
        try:
            publisher, created = collect.add_publisher(session, url)
        except QueueError as exc:
            raise ToolError(str(exc))
    state = "active" if publisher.is_active else "inactive"
    if not created:
        return f"Already have {publisher.slug} ({publisher.kind.value}, {state})"
    log(f"  add_publisher {publisher.slug}: {reason.strip()}")
    return f"Added {publisher.slug} ({publisher.kind.value}, {state})"
