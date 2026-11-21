"""MarkTechPost is an aggregator

Its posts retell other people's releases: 0 loves in 5 hand-labelled items, and
the agent rejects most as retellings. As an aggregator its feed is still
polled, but what is queued is the first repo, paper, model or docs link in
each post, credited to its own site (ADR 22).

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-11-21 00:00:00.000000

"""
from __future__ import annotations

from alembic import op

revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE publisher SET type = 'ainews', kind = 'community'"
        " WHERE slug = 'marktechpost'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE publisher SET type = 'rss', kind = 'media' WHERE slug = 'marktechpost'"
    )
