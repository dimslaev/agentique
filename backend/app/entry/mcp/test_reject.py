"""The `reject` tool: the verdict it writes, and an unknown URL as a tool error."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.ledger import Reject, RejectStage
from app.entry.mcp.reject import reject


@pytest.mark.usefixtures("curator")
def test_reject_settles_the_candidate(db: Session, candidate: Reject) -> None:
    assert reject(candidate.url, 22, "A vendor tutorial.") == (
        f"Rejected [22/100] {candidate.url}"
    )
    db.expire_all()
    row = db.get(Reject, candidate.url)
    assert row is not None
    assert (row.stage, row.score, row.reason) == (
        RejectStage.below_threshold,
        22,
        "A vendor tutorial.",
    )


@pytest.mark.usefixtures("curator")
def test_reject_refuses_a_url_nobody_queued() -> None:
    with pytest.raises(ToolError, match="No candidate for"):
        reject("https://never-queued.example/post", 22, "r")
