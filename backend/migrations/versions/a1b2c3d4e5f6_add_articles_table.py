"""Add articles table with pgvector

Revision ID: a1b2c3d4e5f6
Revises: fe56fa70289e
Create Date: 2026-06-27 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "article",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("categories", sa.JSON(), nullable=True),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "embedding",
            sa.VARCHAR(length=256),  # placeholder; vector type applied below
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Replace placeholder column with the real vector type
    op.execute("ALTER TABLE article ALTER COLUMN embedding TYPE vector(256) USING NULL")

    op.create_index("ix_article_score", "article", ["score"])
    op.create_index("ix_article_published_at", "article", ["published_at"])
    op.execute(
        """
        CREATE INDEX ix_article_embedding_hnsw
        ON article
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.drop_table("article")
