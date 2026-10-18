"""Normalize article: publisher FK, tag vocabulary, enum columns

Destructive by design. `article` is dropped and recreated in the new shape
(`publisher_id` FK instead of the old `source` / `source_type` strings), so
every existing article and like is lost. That is fine for fresh / test / CI
databases, which is all this revision is meant to serve.

Production is *not* migrated by this revision — it gets the prepared dump
swapped in, followed by `alembic stamp head`.

Revision ID: b2c3d4e5f6a7
Revises: a7b8c9d0e1f2
Create Date: 2026-07-09 00:00:00.000000

"""

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # article_like FKs article(id), so it has to go first
    op.execute("DROP TABLE IF EXISTS article_like")
    op.execute("DROP TABLE IF EXISTS article")

    op.execute(
        "CREATE TYPE publisherkind AS ENUM "
        "('individual', 'company', 'community', 'media')"
    )
    op.execute("CREATE TYPE trustlevel AS ENUM ('low', 'medium', 'high')")
    op.execute(
        "CREATE TYPE articlekind AS ENUM "
        "('blog', 'product', 'announcement', 'repo', 'paper', 'model')"
    )

    op.execute(
        """
        CREATE TABLE publisher (
            id SERIAL PRIMARY KEY,
            slug VARCHAR NOT NULL,
            name VARCHAR NOT NULL,
            kind publisherkind NOT NULL,
            description VARCHAR,
            image VARCHAR,
            links JSON NOT NULL DEFAULT '{}',
            trust trustlevel NOT NULL DEFAULT 'medium',
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE article (
            id SERIAL PRIMARY KEY,
            title VARCHAR NOT NULL,
            url VARCHAR NOT NULL,
            publisher_id INTEGER NOT NULL REFERENCES publisher (id),
            published_at TIMESTAMPTZ,
            score INTEGER NOT NULL,
            kind articlekind NOT NULL DEFAULT 'blog',
            categories JSON NOT NULL DEFAULT '[]',
            summary VARCHAR,
            content VARCHAR,
            embedding vector(256),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE tag (
            id SERIAL PRIMARY KEY,
            slug VARCHAR NOT NULL UNIQUE,
            name VARCHAR NOT NULL,
            description VARCHAR
        )
        """
    )

    op.execute(
        """
        CREATE TABLE article_tag (
            article_id INTEGER NOT NULL REFERENCES article (id),
            tag_id INTEGER NOT NULL REFERENCES tag (id),
            PRIMARY KEY (article_id, tag_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE article_like (
            user_id UUID NOT NULL REFERENCES "user" (id),
            article_id INTEGER NOT NULL REFERENCES article (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, article_id)
        )
        """
    )

    op.execute("CREATE INDEX ix_article_score ON article (score)")
    op.execute("CREATE INDEX ix_article_published_at ON article (published_at)")
    op.execute(
        """
        CREATE INDEX ix_article_embedding_hnsw
        ON article
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS article_like")
    op.execute("DROP TABLE IF EXISTS article_tag")
    op.execute("DROP TABLE IF EXISTS tag")
    op.execute("DROP TABLE IF EXISTS article")
    op.execute("DROP TABLE IF EXISTS publisher")

    op.execute("DROP TYPE IF EXISTS articlekind")
    op.execute("DROP TYPE IF EXISTS trustlevel")
    op.execute("DROP TYPE IF EXISTS publisherkind")

    # restore the pre-normalization shapes (a1b2c3d4e5f6 + d4e5f6a7b8c9)
    op.execute(
        """
        CREATE TABLE article (
            id SERIAL PRIMARY KEY,
            title VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            source_type VARCHAR NOT NULL,
            url VARCHAR,
            published_at TIMESTAMPTZ,
            score INTEGER,
            summary TEXT,
            categories JSON,
            kind VARCHAR,
            content TEXT,
            embedding vector(256),
            created_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX ix_article_score ON article (score)")
    op.execute("CREATE INDEX ix_article_published_at ON article (published_at)")
    op.execute(
        """
        CREATE INDEX ix_article_embedding_hnsw
        ON article
        USING hnsw (embedding vector_cosine_ops)
        """
    )

    op.execute(
        """
        CREATE TABLE article_like (
            user_id UUID NOT NULL REFERENCES "user" (id),
            article_id INTEGER NOT NULL REFERENCES article (id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, article_id)
        )
        """
    )
