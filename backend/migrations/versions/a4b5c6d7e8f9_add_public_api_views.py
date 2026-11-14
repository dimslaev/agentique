"""add public_api views

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-11-14 00:00:01.000000

"""
from alembic import op

revision = "a4b5c6d7e8f9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS public_api")
    # No content, score_reason or embedding. The like count is a number, not
    # who liked. Enums are text so a query needs no type from `public`.
    op.execute(
        """
        CREATE OR REPLACE VIEW public_api.article AS
        SELECT
            a.id,
            a.title,
            a.url,
            a.publisher_id,
            a.published_at,
            a.score,
            a.kind::text AS kind,
            a.summary,
            (
                SELECT count(*)::int FROM public.article_like l
                WHERE l.article_id = a.id
            ) AS like_count
        FROM public.article a
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW public_api.publisher AS
        SELECT id, slug, name, kind::text AS kind FROM public.publisher
        """
    )
    op.execute(
        "CREATE OR REPLACE VIEW public_api.tag AS "
        "SELECT id, slug, name FROM public.tag"
    )
    op.execute(
        "CREATE OR REPLACE VIEW public_api.article_tag AS "
        "SELECT article_id, tag_id FROM public.article_tag"
    )


def downgrade():
    op.execute("DROP SCHEMA IF EXISTS public_api CASCADE")
