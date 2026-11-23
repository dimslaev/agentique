"""Add the Bluesky source: the `bluesky` publisher type and its publisher row

Bluesky is an aggregator like Hacker News: an item is credited to the site it
links to, and the row only holds what links to nothing we know.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-11-23 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The INSERT uses the new label, so it has to be committed first.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE publishertype ADD VALUE IF NOT EXISTS 'bluesky'")
    op.execute(
        """
        INSERT INTO publisher (slug, name, kind, type, links, trust, is_active, topic_gated, created_at)
        VALUES ('bluesky', 'Bluesky', 'community', 'bluesky',
                '{"website": "https://bsky.app"}', 'medium', true, false, now())
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # The enum label stays: Postgres cannot drop one.
    op.execute("DELETE FROM publisher WHERE slug = 'bluesky'")
