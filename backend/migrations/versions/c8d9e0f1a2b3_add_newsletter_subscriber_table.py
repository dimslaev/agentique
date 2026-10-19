"""add newsletter_subscriber table

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-06-30 00:00:00.000000

"""
from alembic import op

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS newsletter_subscriber (
            email TEXT PRIMARY KEY,
            categories JSONB NOT NULL DEFAULT '["all"]',
            custom_category TEXT NOT NULL DEFAULT '',
            utm_source TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS newsletter_subscriber")
