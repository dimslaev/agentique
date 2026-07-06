"""add pipeline_run table

Revision ID: f1a2b3c4d5e6
Revises: d4e5f6a7b8c9
Create Date: 2026-07-06 00:00:00.000000

"""
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pipeline_run (
            id SERIAL PRIMARY KEY,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ,
            duration_ms INTEGER,
            ok BOOLEAN NOT NULL DEFAULT false,
            sources JSONB NOT NULL DEFAULT '[]'::jsonb
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS pipeline_run")
