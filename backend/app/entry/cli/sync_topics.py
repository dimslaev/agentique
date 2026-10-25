"""Create any missing newsletter topic in Resend, once per environment.

Each topic is born with `default_subscription: opt_in`, which Resend never
lets change, so this is run by hand after review - never from deploy:

    cd backend && python -m app.entry.cli.sync_topics
"""

from __future__ import annotations

import sys

from app.features.newsletter.model import IssueError
from app.features.newsletter.topics import TOPICS, create_missing


def main() -> None:
    try:
        created = create_missing()
    except IssueError as e:
        sys.exit(str(e))
    for slug, topic_id in created:
        print(f"created {slug}: {topic_id}")
    print(f"{len(TOPICS) - len(created)} already existed.")


if __name__ == "__main__":
    main()
