"""Add publisher.topic_gated (drop off-topic titles before they cost an LLM call)

Marks a publisher whose feed is mostly not about AI — a general engineering
blog rather than an AI one. The fetch step title-gates those feeds against
AI_TITLE_KEYWORDS; every existing publisher was added because it is on-topic,
so the backfill is a plain false.

Revision ID: e3f4a5b6c7d8
Revises: c1d2e3f4a5b6
Create Date: 2026-08-31 00:00:00.000000

"""

from alembic import op

revision = "e3f4a5b6c7d8"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # DEFAULT false in the ADD backfills existing rows in one pass, and is kept
    # afterwards so a non-ORM insert (raw SQL, a dump restore) is safe on a
    # NOT NULL column — same shape as publisher.type's default.
    op.execute(
        "ALTER TABLE publisher ADD COLUMN topic_gated boolean NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE publisher DROP COLUMN topic_gated")
