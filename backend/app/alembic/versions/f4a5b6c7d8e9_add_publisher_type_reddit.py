"""Add 'reddit' to the publishertype enum

The Reddit source (r/LocalLLaMA, r/MachineLearning) is its own ingestion
channel like Hacker News is, not an rss feed and not "other".

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-08-31 00:00:00.000000

"""

from alembic import op

revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres allows ADD VALUE inside a transaction as long as the new label
    # is not also *used* in it — this migration only declares it.
    op.execute("ALTER TYPE publishertype ADD VALUE IF NOT EXISTS 'reddit'")


def downgrade() -> None:
    # Postgres cannot drop an enum label. Reverting would mean rebuilding the
    # type and every column using it, which is not worth it for an unused
    # label — so this is deliberately a no-op.
    pass
