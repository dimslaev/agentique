#! /usr/bin/env bash
set -e
set -x

python -m app.entry.cli.wait_for_db

bash "$(dirname "$0")/test.sh" "$@"
