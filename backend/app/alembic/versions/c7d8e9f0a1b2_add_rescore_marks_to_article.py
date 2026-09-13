"""Track the article rescore and mark low scorers for deletion

rescored_at is what makes scripts/rescore_articles.py resumable: it only picks
rows where it is null. marked_for_deletion_at is a flag for a human to review,
not a soft delete - the feed does not read it.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-09-13 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "c7d8e9f0a1b2"
down_revision = "b6c7d8e9f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE article
            ADD COLUMN IF NOT EXISTS rescored_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS marked_for_deletion_at TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE article
            DROP COLUMN IF EXISTS rescored_at,
            DROP COLUMN IF EXISTS marked_for_deletion_at
        """
    )
