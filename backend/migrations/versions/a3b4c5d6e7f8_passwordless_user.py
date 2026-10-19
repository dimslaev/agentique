"""passwordless user: login_token replaces hashed_password

Revision ID: a3b4c5d6e7f8
Revises: fa1b2c3d4e5f
Create Date: 2026-10-03 12:00:00.000000

"""

import secrets

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a3b4c5d6e7f8"
down_revision = "fa1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user", sa.Column("login_token", sa.String(length=64), nullable=True)
    )
    conn = op.get_bind()
    user = sa.table("user", sa.column("id", sa.Uuid), sa.column("login_token"))
    for (user_id,) in conn.execute(sa.select(user.c.id)).all():
        conn.execute(
            user.update()
            .where(user.c.id == user_id)
            .values(login_token=secrets.token_urlsafe(32))
        )
    op.alter_column("user", "login_token", nullable=False)
    op.create_index(
        op.f("ix_user_login_token"), "user", ["login_token"], unique=True
    )
    op.drop_column("user", "hashed_password")


def downgrade():
    # Passwords are gone for good: a downgrade leaves every account with an
    # unusable hash, to be reset by hand.
    op.add_column(
        "user",
        sa.Column(
            "hashed_password",
            sa.String(),
            nullable=False,
            server_default="!",
        ),
    )
    op.alter_column("user", "hashed_password", server_default=None)
    op.drop_index(op.f("ix_user_login_token"), table_name="user")
    op.drop_column("user", "login_token")
