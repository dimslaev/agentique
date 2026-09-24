"""Keep the links an article body makes on scored_url

The repo / model / paper / docs links extraction finds, grouped, so the
curation agent reads them beside the text instead of fetching the page again.
Nullable: rows already there were extracted without them.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-09-23 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scored_url ADD COLUMN IF NOT EXISTS links JSON")


def downgrade() -> None:
    op.execute("ALTER TABLE scored_url DROP COLUMN IF EXISTS links")
