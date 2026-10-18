"""add pro_until to user

Revision ID: e7f8a9b0c1d2
Revises: 3b3ed3a25c85
Create Date: 2026-07-19 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7f8a9b0c1d2"
down_revision = "3b3ed3a25c85"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user", sa.Column("pro_until", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade():
    op.drop_column("user", "pro_until")
