"""add mcp_token table

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-11-14 00:00:00.000000

"""
from alembic import op

revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS mcp_token (
            user_id UUID PRIMARY KEY REFERENCES "user" (id) ON DELETE CASCADE,
            token_hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_mcp_token_token_hash "
        "ON mcp_token (token_hash)"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS mcp_token")
