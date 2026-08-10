"""add feed_item table

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-08-10 00:00:00.000000

"""

from alembic import op

revision = "d1e2f3a4b5c6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TYPE feeditemstatus AS ENUM ('new', 'accepted', 'rejected')")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS feed_item (
            id SERIAL PRIMARY KEY,
            url VARCHAR NOT NULL UNIQUE,
            title VARCHAR NOT NULL,
            content VARCHAR,
            published_at TIMESTAMPTZ,
            feed_publisher_id INTEGER REFERENCES publisher (id),
            links JSON NOT NULL DEFAULT '[]',
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status feeditemstatus NOT NULL DEFAULT 'new',
            decision VARCHAR,
            decided_at TIMESTAMPTZ
        )
        """
    )
    # The agent pulls its batches off `status`; the prune job scans `fetched_at`.
    op.execute("CREATE INDEX IF NOT EXISTS ix_feed_item_status ON feed_item (status)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feed_item_fetched_at ON feed_item (fetched_at)"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS feed_item")
    op.execute("DROP TYPE IF EXISTS feeditemstatus")
