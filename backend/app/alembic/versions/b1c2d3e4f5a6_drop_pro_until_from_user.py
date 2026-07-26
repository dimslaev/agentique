"""drop pro_until from user

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-07-26 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("user", "pro_until")


def downgrade():
    op.add_column(
        "user", sa.Column("pro_until", sa.DateTime(timezone=True), nullable=True)
    )
