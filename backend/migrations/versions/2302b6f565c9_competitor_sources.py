"""Poll AI/TLDR

AI/TLDR arrives by mail from
ai-tldr@buttondown.email; its row existed, inactive with only a website link,
so it gets the email link and goes through the newsletter source.

Revision ID: 2302b6f565c9
Revises: c0d1e2f3a4b5
Create Date: 2026-11-25 00:00:00.000000

"""

from __future__ import annotations

from alembic import op

revision = "2302b6f565c9"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO publisher (slug, name, kind, type, links, trust, is_active, topic_gated, created_at)
        SELECT 'ai-tldr-dev', 'AI/TLDR', 'media', 'email', '{}', 'medium', true, false, now()
        WHERE NOT EXISTS (SELECT 1 FROM publisher WHERE slug = 'ai-tldr-dev')
        """
    )
    op.execute(
        """
        UPDATE publisher
        SET name = 'AI/TLDR', kind = 'media', type = 'email', is_active = true,
            links = '{"email": "ai-tldr@buttondown.email", "website": "https://ai-tldr.dev"}'
        WHERE slug = 'ai-tldr-dev'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE publisher
        SET name = 'ai-tldr.dev', kind = 'unknown', type = 'other', is_active = false,
            links = '{"website": "https://ai-tldr.dev"}'
        WHERE slug = 'ai-tldr-dev'
        """
    )
