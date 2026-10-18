#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python -m app.entry.cli.wait_for_db

# Run migrations
alembic upgrade head

# Create initial data in DB
python -m app.entry.cli.create_superuser

# Load the tag vocabulary (all environments; the pipeline requires it)
python -m app.entry.cli.seed_tags

# Seed sample articles for local/CI (module also self-guards on production)
if [ "$ENVIRONMENT" != "production" ]; then
    python -m app.entry.cli.seed_articles
fi
