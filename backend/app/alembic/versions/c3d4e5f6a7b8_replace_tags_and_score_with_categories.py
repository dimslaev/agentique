"""Replace tags + score with the category vocabulary

The pipeline no longer scores articles 1-100 and no longer assigns tags from a
43-entry vocabulary. It asks one question instead — does this article match one
of our categories? — and stores nothing that matches none. So the score column,
the dev/models/research `categories` JSON, and the whole tag vocabulary go, and
a `category` table plus an `article_category` join take their place.

Destructive: `tag`, `article_tag`, `article.score` and `article.categories` are
dropped along with their data. Existing articles survive with no categories
until they are backfilled (see scripts/backfill_categories.py) — they are
reachable by search and by publisher, but appear in no lane.

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-07-28
"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("exemplars", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "article_category",
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["article.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"]),
        sa.PrimaryKeyConstraint("article_id", "category_id"),
    )
    # Every lane query is "newest in this category", so the join table is read
    # category-first.
    op.create_index(
        "ix_article_category_category_id", "article_category", ["category_id"]
    )

    op.drop_table("article_tag")
    op.drop_table("tag")

    op.drop_index("ix_article_score", table_name="article")
    op.drop_column("article", "score")
    op.drop_column("article", "categories")


def downgrade():
    op.add_column(
        "article",
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "article",
        sa.Column("categories", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_article_score", "article", ["score"])

    op.create_table(
        "tag",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_table(
        "article_tag",
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["article.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tag.id"]),
        sa.PrimaryKeyConstraint("article_id", "tag_id"),
    )

    op.drop_index("ix_article_category_category_id", table_name="article_category")
    op.drop_table("article_category")
    op.drop_table("category")
