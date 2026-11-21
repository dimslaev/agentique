"""add publisher disabled_reason and switched_at

Revision ID: b5c6d7e8f9a1
Revises: a4b5c6d7e8f9
Create Date: 2026-11-21 00:00:00.000000

"""
from __future__ import annotations

from alembic import op

revision = "b5c6d7e8f9a1"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE publisher ADD COLUMN IF NOT EXISTS disabled_reason VARCHAR")
    op.execute("ALTER TABLE publisher ADD COLUMN IF NOT EXISTS switched_at TIMESTAMPTZ")
    # An inactive publisher that already carries a feed or search link was
    # switched off by a person. Mark it so discovery never turns it back on.
    op.execute(
        """
        UPDATE publisher SET disabled_reason = 'pre-existing, off by hand'
        WHERE NOT is_active AND disabled_reason IS NULL
          AND (links::jsonb ?| array['rss', 'substack', 'search'])
        """
    )


def downgrade():
    op.execute("ALTER TABLE publisher DROP COLUMN IF EXISTS switched_at")
    op.execute("ALTER TABLE publisher DROP COLUMN IF EXISTS disabled_reason")
