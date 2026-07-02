#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python app/backend_pre_start.py

# Run migrations
alembic upgrade head

# Create initial data in DB
python app/initial_data.py

# Seed sample articles for local/CI (module also self-guards on production)
if [ "$ENVIRONMENT" != "production" ]; then
    python -m app.seed_articles
fi
