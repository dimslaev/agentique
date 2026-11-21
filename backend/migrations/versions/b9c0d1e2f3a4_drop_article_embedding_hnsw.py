"""Drop the article embedding HNSW index

Search no longer ranks by embedding, and the curation tools compare vectors in
numpy, so nothing queries the index.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-11-21 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_article_embedding_hnsw")


def downgrade() -> None:
    op.execute(
        "CREATE INDEX ix_article_embedding_hnsw ON article"
        " USING hnsw (embedding vector_cosine_ops)"
    )
