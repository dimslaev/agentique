"""Add publisher.type (ingestion source: rss/substack/search/hn/email/ainews/other)

Backfilled from each publisher's links (custom-domain substacks identified by
probing feeds), then set NOT NULL with a server default.

Revision ID: f9a0b1c2d3e4
Revises: e7f8a9b0c1d2
Create Date: 2026-07-22 00:00:00.000000

"""

from alembic import op

revision = "f9a0b1c2d3e4"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TYPE publishertype AS ENUM "
        "('rss', 'substack', 'search', 'hn', 'email', 'ainews', 'other')"
    )
    op.execute("ALTER TABLE publisher ADD COLUMN type publishertype")

    # Backfill from each publisher's links. This runs *before* the substack->rss
    # link normalization, so the 'substack' key is still present to classify on.
    # A substack link (or an rss link on a substack.com host) is its own
    # 'substack' type — kept distinct because once a custom-domain substack is
    # normalized to a bare rss feed we can no longer tell it apart. Custom-domain
    # substacks give nothing away in the URL, so the slug list below was
    # determined by probing each rss feed for Substack markers (substackcdn.com
    # images + the Substack generator tag). A first-party 'search' link is a
    # lab-watch source; an 'email' link is a newsletter sender; smol.ai's AI News
    # is its own ainews source; the HN front page is its own source; everything
    # else (website-only) collapses to 'other'.
    op.execute(
        """
        UPDATE publisher SET type = CASE
            WHEN links::jsonb ? 'search' THEN 'search'
            WHEN links::jsonb ? 'substack'
                OR links->>'rss' LIKE '%.substack.com%'
                OR slug IN (
                    'ahead-of-ai', 'ai-by-aakash', 'ai-by-hand', 'ai-disruption',
                    'ai-newsletter', 'artificial-corner', 'ben-s-bites',
                    'bytebytego-newsletter', 'diamantai', 'digital-thoughts',
                    'mlwhiz', 'product-growth', 'swirlai-newsletter',
                    'the-ai-engineer', 'the-generative-programmer',
                    'toxsec-ai-and-cybersecurity', 'understanding-ai',
                    'vik-s-newsletter'
                )
                THEN 'substack'
            WHEN links::jsonb ? 'rss' THEN 'rss'
            WHEN links::jsonb ? 'email' THEN 'email'
            WHEN slug = 'ai-news' THEN 'ainews'
            WHEN lower(links->>'website') LIKE '%news.ycombinator.com%' THEN 'hn'
            ELSE 'other'
        END::publishertype
        """
    )

    op.execute("ALTER TABLE publisher ALTER COLUMN type SET NOT NULL")
    # server default so any non-ORM insert (raw SQL, restore) is safe on a
    # NOT NULL column; mirrors the model default (PublisherType.other).
    op.execute("ALTER TABLE publisher ALTER COLUMN type SET DEFAULT 'other'")


def downgrade() -> None:
    op.execute("ALTER TABLE publisher DROP COLUMN type")
    op.execute("DROP TYPE IF EXISTS publishertype")
