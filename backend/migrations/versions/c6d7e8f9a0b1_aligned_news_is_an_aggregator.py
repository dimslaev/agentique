"""Aligned News is an aggregator

Its feed is links to other people's posts (model cards, launch pages, tweets),
but as an rss publisher every item was credited to it: the AssemblyAI and
OpenMed releases approved on 2026-11-20 show "Aligned News" as their publisher.
As an aggregator, an item is credited to the site its URL is on, and the cull
skips it, since its own approval count no longer measures it.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a1
Create Date: 2026-11-21 00:00:00.000000

"""

from alembic import op

revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE publisher SET type = 'ainews' WHERE slug = 'aligned-news'")


def downgrade() -> None:
    op.execute("UPDATE publisher SET type = 'rss' WHERE slug = 'aligned-news'")
