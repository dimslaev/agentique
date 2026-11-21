"""The `discovery_candidates` tool: publishers to probe and feeds to cull."""

from __future__ import annotations

from sqlmodel import Session

from app.core.db.engine import engine
from app.features.curation import service as curation


def discovery_candidates(limit: int = 30) -> dict[str, list[dict[str, str]]]:
    """What the discovery routine decides from.

    `probe`: up to `limit` inactive publishers worth reading, the most
    approvals first. Each has `slug`, `name`, `kind`, `approved` (approvals /
    decisions over 90 days), `website`, `last_approval`, and `disabled_reason`
    when a newer approval reopened one switched off before. Firehoses whose
    rate a probe cannot lift to 40% are already left out. `cull`: active feed
    publishers to switch off, each with the `reason` to pass to
    `disable_publisher`.
    """
    with Session(engine) as session:
        return curation.discovery_candidates(session, limit)
