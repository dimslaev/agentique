"""Normalize substack publisher links to ready-to-poll rss feed URLs

Every publisher whose links carry a ``substack`` key gets it rewritten to an
``rss`` key holding the ``/feed`` endpoint (substack serves the HTML site at the
bare URL, the feed at ``/feed``). This bakes in what ``pipeline.utils.feed_url``
used to do at read time, so that helper can go away and there is a single ``rss``
link to poll.

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
Create Date: 2026-07-22 00:00:00.000000

"""

from alembic import op

revision = "a0b1c2d3e4f5"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the 'substack' key, add an 'rss' key = <url stripped of trailing '/'>
    # with '/feed' appended unless it is already there.
    op.execute(
        """
        UPDATE publisher
        SET links = (
            (links::jsonb - 'substack')
            || jsonb_build_object(
                'rss',
                CASE
                    WHEN rtrim(links->>'substack', '/') LIKE '%/feed'
                        THEN rtrim(links->>'substack', '/')
                    ELSE rtrim(links->>'substack', '/') || '/feed'
                END
            )
        )::json
        WHERE links::jsonb ? 'substack'
        """
    )


def downgrade() -> None:
    # Best effort: move *.substack.com feed links back to a 'substack' key with
    # the '/feed' suffix removed. Custom-domain substacks can't be recovered.
    op.execute(
        """
        UPDATE publisher
        SET links = (
            (links::jsonb - 'rss')
            || jsonb_build_object(
                'substack', regexp_replace(links->>'rss', '/feed$', '')
            )
        )::json
        WHERE links->>'rss' LIKE '%.substack.com/feed'
        """
    )
