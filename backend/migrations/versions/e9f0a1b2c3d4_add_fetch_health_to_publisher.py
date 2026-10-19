"""Keep each publisher's fetch health on its own row

When its feed last answered, when it last gave the run a new candidate, and the
error it last failed with. Replaces the per-publisher list pipeline_run stored
on every run; that column stays, unwritten, with its default.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-09-23 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE publisher
            ADD COLUMN IF NOT EXISTS last_fetched_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS last_new_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS last_error VARCHAR
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE publisher
            DROP COLUMN IF EXISTS last_fetched_at,
            DROP COLUMN IF EXISTS last_new_at,
            DROP COLUMN IF EXISTS last_error
        """
    )
