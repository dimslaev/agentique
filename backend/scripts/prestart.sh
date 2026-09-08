#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python scripts/wait_for_db.py

# Run migrations
alembic upgrade head

# Create initial data in DB
python scripts/create_superuser.py

# Load the tag vocabulary (all environments; the pipeline requires it)
python scripts/seed_tags.py

# Seed sample articles for local/CI (module also self-guards on production)
if [ "$ENVIRONMENT" != "production" ]; then
    python scripts/seed_articles.py
fi
