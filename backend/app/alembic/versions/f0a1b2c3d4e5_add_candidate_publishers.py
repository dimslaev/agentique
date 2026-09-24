"""Add candidate publishers, inactive, for a trial before they are polled

Hosts the curation agent kept approving while no publisher claimed them (found
through Hacker News or a newsletter), plus writers from the ai-tldr.dev
influencer list. All inactive: the run never polls them, but crediting by URL
reads every publisher, so an article on one of these hosts counts as its
author's from now on and builds the approval record a trial is judged on.

A feed link is set only where it is known. The rest carry a website link alone
until a feed is found. Labs with no feed use lab watch (a ``search`` domain).

Also gives AI in public its own domain, which it publishes on beside its
substack.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-09-24 00:00:00.000000

"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "f0a1b2c3d4e5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None

# (slug, name, kind, type, links)
PUBLISHERS = [
    ("tim-dettmers", "Tim Dettmers", "individual", "rss", {"rss": "https://timdettmers.com/feed/", "website": "https://timdettmers.com"}),
    ("sankalp", "Sankalp", "individual", "rss", {"rss": "https://sankalp.bearblog.dev/feed/", "website": "https://sankalp.bearblog.dev"}),
    ("jay-alammar", "Jay Alammar", "individual", "rss", {"rss": "https://jalammar.github.io/feed.xml", "website": "https://jalammar.github.io"}),
    ("vivek-haldar", "Vivek Haldar", "individual", "rss", {"website": "https://vivekhaldar.com"}),
    ("aleksa-gordic", "Aleksa Gordić", "individual", "rss", {"website": "https://aleksagordic.com"}),
    ("fergus-finn", "Fergus Finn", "individual", "rss", {"website": "https://fergusfinn.com"}),
    ("james-padolsey", "James Padolsey", "individual", "rss", {"website": "https://blog.j11y.io"}),
    ("fabrizio-ferri-benedetti", "Fabrizio Ferri Benedetti", "individual", "rss", {"website": "https://passo.uno"}),
    ("ivan-pleshkov", "Ivan Pleshkov", "individual", "rss", {"website": "https://ivanpleshkov.dev"}),
    ("maxime-labonne", "Maxime Labonne", "individual", "rss", {"website": "https://mlabonne.github.io/blog"}),
    ("eric-hartford", "Eric Hartford", "individual", "rss", {"website": "https://erichartford.com"}),
    ("jason-wei", "Jason Wei", "individual", "rss", {"website": "https://www.jasonwei.net"}),
    ("answer-ai", "Answer.AI", "company", "rss", {"website": "https://www.answer.ai"}),
    ("claude", "Claude", "company", "search", {"search": "claude.com", "website": "https://claude.com"}),
    ("google-for-developers-blog", "Google for Developers Blog", "company", "search", {"search": "developers.googleblog.com", "website": "https://developers.googleblog.com"}),
    ("nvidia-newsroom", "NVIDIA Newsroom", "company", "search", {"search": "nvidianews.nvidia.com", "website": "https://nvidianews.nvidia.com"}),
    ("artificial-analysis", "Artificial Analysis", "company", "search", {"search": "artificialanalysis.ai", "website": "https://artificialanalysis.ai"}),
    ("unsloth", "Unsloth", "company", "search", {"search": "unsloth.ai", "website": "https://unsloth.ai"}),
    ("kapa-ai", "Kapa.ai", "company", "search", {"search": "kapa.ai", "website": "https://kapa.ai"}),
    ("aikido-security", "Aikido Security", "company", "search", {"search": "aikido.dev", "website": "https://aikido.dev"}),
    ("xiaomi-mimo", "Xiaomi MiMo", "company", "search", {"search": "mimo.xiaomi.com", "website": "https://mimo.xiaomi.com"}),
    ("mozilla-ai", "Mozilla.ai", "company", "search", {"search": "blog.mozilla.ai", "website": "https://blog.mozilla.ai"}),
    ("liquid-ai", "Liquid AI", "company", "search", {"search": "liquid.ai", "website": "https://liquid.ai"}),
    ("sarvam-ai", "Sarvam AI", "company", "search", {"search": "sarvam.ai", "website": "https://sarvam.ai"}),
    ("black-forest-labs", "Black Forest Labs", "company", "search", {"search": "bfl.ai", "website": "https://bfl.ai"}),
    ("sakana-ai", "Sakana AI", "company", "search", {"search": "sakana.ai", "website": "https://sakana.ai"}),
    ("cline", "Cline", "company", "search", {"search": "cline.bot", "website": "https://cline.bot"}),
    ("strix", "Strix", "company", "search", {"search": "strix.ai", "website": "https://strix.ai"}),
    ("noma-security", "Noma Security", "company", "search", {"search": "noma.security", "website": "https://noma.security"}),
]  # fmt: skip


def upgrade() -> None:
    insert = sa.text(
        """
        INSERT INTO publisher (slug, name, kind, type, links, is_active)
        VALUES (
            :slug, :name,
            CAST(:kind AS publisherkind), CAST(:type AS publishertype),
            CAST(:links AS json), false
        )
        ON CONFLICT (slug) DO NOTHING
        """
    )
    for slug, name, kind, type_, links in PUBLISHERS:
        op.execute(
            insert.bindparams(
                slug=slug, name=name, kind=kind, type=type_, links=json.dumps(links)
            )
        )
    op.execute(
        """
        UPDATE publisher
        SET links = (links::jsonb || '{"website": "https://aiinpublic.com"}')::json
        WHERE slug = 'ai-in-public' AND NOT links::jsonb ? 'website'
        """
    )


def downgrade() -> None:
    # A publisher an article or reject already points at stays.
    op.execute(
        sa.text(
            """
            DELETE FROM publisher p
            WHERE p.slug IN :slugs
              AND NOT EXISTS (SELECT 1 FROM article a WHERE a.publisher_id = p.id)
              AND NOT EXISTS (SELECT 1 FROM scored_url s WHERE s.publisher_id = p.id)
            """
        ).bindparams(sa.bindparam("slugs", [p[0] for p in PUBLISHERS], expanding=True))
    )
    op.execute(
        """
        UPDATE publisher
        SET links = (links::jsonb - 'website')::json
        WHERE slug = 'ai-in-public' AND links->>'website' = 'https://aiinpublic.com'
        """
    )
