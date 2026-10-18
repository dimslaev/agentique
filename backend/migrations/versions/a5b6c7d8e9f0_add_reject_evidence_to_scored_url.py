"""Keep the evidence on scored_url, not just the URL

A rejected article used to leave only its URL behind, so there was no telling
why it was dropped or what the scorer saw. Every new column is nullable: the
rows already there carry only a URL and cannot be backfilled.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-09-13 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE scored_url
            ADD COLUMN IF NOT EXISTS stage VARCHAR,
            ADD COLUMN IF NOT EXISTS title VARCHAR,
            ADD COLUMN IF NOT EXISTS source VARCHAR,
            ADD COLUMN IF NOT EXISTS publisher_id INTEGER REFERENCES publisher(id),
            ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS content VARCHAR,
            ADD COLUMN IF NOT EXISTS traction VARCHAR,
            ADD COLUMN IF NOT EXISTS score INTEGER,
            ADD COLUMN IF NOT EXISTS reason VARCHAR,
            ADD COLUMN IF NOT EXISTS detail JSON
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE scored_url
            DROP COLUMN IF EXISTS stage,
            DROP COLUMN IF EXISTS title,
            DROP COLUMN IF EXISTS source,
            DROP COLUMN IF EXISTS publisher_id,
            DROP COLUMN IF EXISTS published_at,
            DROP COLUMN IF EXISTS content,
            DROP COLUMN IF EXISTS traction,
            DROP COLUMN IF EXISTS score,
            DROP COLUMN IF EXISTS reason,
            DROP COLUMN IF EXISTS detail
        """
    )
