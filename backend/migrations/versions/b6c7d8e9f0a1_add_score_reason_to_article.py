"""Keep the scorer's reason on the article, not only on rejects

Nullable: articles scored before the scorer returned a reason have none.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-09-13 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "b6c7d8e9f0a1"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE article ADD COLUMN IF NOT EXISTS score_reason VARCHAR")


def downgrade() -> None:
    op.execute("ALTER TABLE article DROP COLUMN IF EXISTS score_reason")
