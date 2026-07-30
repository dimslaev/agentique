"""add publishers column to pipeline_run

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-07-30 00:00:00.000000

"""
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE pipeline_run ADD COLUMN publishers JSONB NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade():
    op.execute("ALTER TABLE pipeline_run DROP COLUMN publishers")
