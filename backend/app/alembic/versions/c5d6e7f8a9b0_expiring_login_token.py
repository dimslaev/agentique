"""expiring sign-in links

Every token already emailed was permanent, so all of them are dropped: a reader
signs in again by asking for a new link.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-10-06 00:00:00.000000

"""

import secrets

import sqlalchemy as sa
from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("login_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "user", "login_token", existing_type=sa.String(length=64), nullable=True
    )
    op.execute('UPDATE "user" SET login_token = NULL')


def downgrade() -> None:
    conn = op.get_bind()
    user = sa.table("user", sa.column("id", sa.Uuid), sa.column("login_token"))
    for (user_id,) in conn.execute(
        sa.select(user.c.id).where(user.c.login_token.is_(None))
    ).all():
        conn.execute(
            user.update()
            .where(user.c.id == user_id)
            .values(login_token=secrets.token_urlsafe(32))
        )
    op.alter_column(
        "user", "login_token", existing_type=sa.String(length=64), nullable=False
    )
    op.drop_column("user", "login_token_expires_at")
