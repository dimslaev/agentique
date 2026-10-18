"""add analytics_event table

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-07-06 00:00:00.000000

"""
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_event (
            id SERIAL PRIMARY KEY,
            event VARCHAR NOT NULL DEFAULT 'pageview',
            path VARCHAR,
            referrer VARCHAR,
            visitor_id VARCHAR,
            user_id UUID REFERENCES "user" (id),
            user_agent VARCHAR,
            props JSON NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_analytics_event_event "
        "ON analytics_event (event)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_analytics_event_path "
        "ON analytics_event (path)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_analytics_event_visitor_id "
        "ON analytics_event (visitor_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_analytics_event_created_at "
        "ON analytics_event (created_at)"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS analytics_event")
