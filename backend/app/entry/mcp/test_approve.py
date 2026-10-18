"""The `approve` tool: what it reports, and a refused label as a tool error."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError
from sqlmodel import Session

from app.core.db.ledger import Reject, RejectStage
from app.entry.mcp.approve import approve
from app.features.curation import service as curation


@pytest.mark.usefixtures("curator")
def test_approve_reports_the_article_it_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    def fake(_session: Session, *args: object) -> int:
        calls.append(args)
        return 42

    monkeypatch.setattr(curation, "approve", fake)
    url = "https://example.com/post"
    assert approve(url, 81, "r", "s", "post", ["agents"], "media", "Example") == (
        f"Published article #42: {url}"
    )
    assert calls == [(url, 81, "r", "s", "post", ["agents"], "media", "Example")]


@pytest.mark.usefixtures("curator")
def test_a_refused_label_is_a_tool_error_and_the_candidate_stays(
    db: Session, candidate: Reject
) -> None:
    with pytest.raises(ToolError, match="publisher_kind"):
        approve(candidate.url, 81, "r", "s", "post", [])
    db.expire_all()
    row = db.get(Reject, candidate.url)
    assert row is not None and row.stage == RejectStage.pending
