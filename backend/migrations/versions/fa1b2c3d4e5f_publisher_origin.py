"""Credit articles to their author, not the aggregator that found them

Adds the publisher kinds `lab` and `unknown`, folds the article kinds `blog`,
`product` and `announcement` into `post`, and adds `article.found_via`, filled
here for every article an aggregator is credited with. That has to happen
before the re-credit backfill (`scripts/backfill_publishers.py`) moves those
articles to their authors: the publisher column is the only record of it.

The old enum labels stay in the Postgres types, unused: deploy runs additive
migrations only, and Postgres cannot drop an enum label anyway.

Revision ID: fa1b2c3d4e5f
Revises: e9f0a1b2c3d4
Create Date: 2026-10-03 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "fa1b2c3d4e5f"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A label added in a transaction cannot be used in that same transaction,
    # and the UPDATE below uses 'post'. Committing the labels first lets the
    # whole change ship as one migration.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE publisherkind ADD VALUE IF NOT EXISTS 'lab'")
        op.execute("ALTER TYPE publisherkind ADD VALUE IF NOT EXISTS 'unknown'")
        op.execute("ALTER TYPE articlekind ADD VALUE IF NOT EXISTS 'post'")

    op.execute("ALTER TABLE article ADD COLUMN IF NOT EXISTS found_via VARCHAR")
    op.execute(
        """
        UPDATE article SET found_via = p.name
        FROM publisher p
        WHERE p.id = article.publisher_id
          AND p.type IN ('hn', 'email', 'ainews', 'reddit')
          AND article.found_via IS NULL
        """
    )
    op.execute(
        "UPDATE article SET kind = 'post' "
        "WHERE kind IN ('blog', 'product', 'announcement')"
    )
    op.execute("ALTER TABLE article ALTER COLUMN kind SET DEFAULT 'post'")


def downgrade() -> None:
    # The kind remap and the enum labels are not reverted: which of blog,
    # product or announcement a post was is not recorded anywhere.
    op.execute("ALTER TABLE article ALTER COLUMN kind SET DEFAULT 'blog'")
    op.execute("ALTER TABLE article DROP COLUMN IF EXISTS found_via")
