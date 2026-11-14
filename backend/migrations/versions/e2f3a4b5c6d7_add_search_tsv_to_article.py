"""add search_tsv to article

A full-text index for keyword search. Postgres keeps the column: it is
generated from the title, summary and content, so existing rows get it when
the column is added and no backfill runs.

Adding a stored generated column rewrites `article` under an exclusive lock.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-11-12 00:00:00.000000

"""

from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE article ADD COLUMN search_tsv tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A')
            || setweight(to_tsvector('simple', coalesce(title, '')), 'A')
            || setweight(to_tsvector('english', coalesce(summary, '')), 'B')
            || setweight(to_tsvector('english', coalesce(content, '')), 'D')
        ) STORED
        """
    )
    op.execute("CREATE INDEX ix_article_search_tsv ON article USING gin (search_tsv)")


def downgrade() -> None:
    op.drop_index("ix_article_search_tsv", table_name="article")
    op.drop_column("article", "search_tsv")
