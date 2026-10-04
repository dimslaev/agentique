"""Drop query strings from analytics paths and referrers, rotating leaked sign-in tokens

The tracker logged the full URL, so a visit to a sign-in link stored its token
in ``analytics_event.path``. That token never expires: every account whose
token shows up there gets a fresh one, before the rows that show it are
cleaned. Its owner signs in again by asking for a new link.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-04 00:00:00.000000

"""

import secrets

import sqlalchemy as sa
from alembic import op

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    leaked = conn.execute(
        sa.text(
            """
            SELECT DISTINCT substring(path from '[?&]token=([^&#]+)')
            FROM analytics_event
            WHERE path ~ '[?&]token='
            """
        )
    ).scalars()
    user = sa.table("user", sa.column("login_token"))
    for token in leaked:
        conn.execute(
            user.update()
            .where(user.c.login_token == token)
            .values(login_token=secrets.token_urlsafe(32))
        )

    for column in ("path", "referrer"):
        op.execute(
            f"""
            UPDATE analytics_event
            SET {column} = NULLIF(regexp_replace({column}, '[?#].*$', ''), '')
            WHERE {column} ~ '[?#]'
            """
        )


def downgrade() -> None:
    # The query strings and the replaced tokens are gone for good.
    pass
