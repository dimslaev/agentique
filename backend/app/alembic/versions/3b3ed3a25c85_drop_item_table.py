"""drop item table

Revision ID: 3b3ed3a25c85
Revises: b2c3d4e5f6a7
Create Date: 2026-07-17 23:34:40.835821

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '3b3ed3a25c85'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('item')


def downgrade():
    op.create_table('item',
    sa.Column('description', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('title', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('owner_id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], name=op.f('item_owner_id_fkey'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('item_pkey'))
    )
