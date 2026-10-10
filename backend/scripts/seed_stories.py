"""Seeds two or three stories into a local database, through `save_story`.

With a JSON file argument, saves each `{slug, name, blurb, urls}` in it: write
one by hand against a restored dump. Without one, makes demo stories from the
newest articles, a few per story across publishers, so the rail has something
to show. Never touches production.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

from sqlmodel import Session, col, select

from app.catalog import stories
from app.catalog.models import Article
from app.platform.db import engine
from app.platform.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEMO = [
    (
        "codemode",
        "Codemode",
        "Agents write code that calls their tools instead of calling each tool "
        "in turn. It cuts tokens and round trips on long tasks.",
    ),
    (
        "decision-models",
        "Decision models",
        "Small models trained to pick the next step, not to write the answer. "
        "They make agents cheaper to run at every turn.",
    ),
    (
        "local-inference",
        "Local inference",
        "Running open weights on a laptop or one GPU. Quantized releases now "
        "come the same week as the full model.",
    ),
]
PER_STORY = 4


class StorySpec(TypedDict):
    slug: str
    name: str
    blurb: str
    urls: list[str]


def demo_stories(session: Session) -> list[StorySpec]:
    """Each demo story gets `PER_STORY` of the newest articles, taken round
    robin across publishers so it passes the rail's two-publisher bar."""
    newest = session.exec(
        select(Article).order_by(col(Article.published_at).desc().nulls_last())
    ).all()
    by_publisher: dict[int, list[Article]] = defaultdict(list)
    for article in newest:
        by_publisher[article.publisher_id].append(article)
    queues = list(by_publisher.values())
    picked: list[str] = []
    while len(picked) < PER_STORY * len(DEMO) and any(queues):
        for queue in queues:
            if queue:
                picked.append(queue.pop(0).url)
    return [
        {
            "slug": slug,
            "name": name,
            "blurb": blurb,
            "urls": picked[i * PER_STORY : (i + 1) * PER_STORY],
        }
        for i, (slug, name, blurb) in enumerate(DEMO)
    ]


def main() -> None:
    if settings.ENVIRONMENT == "production":
        raise SystemExit("Refusing to run seed_stories in production.")
    with Session(engine) as session:
        if len(sys.argv) > 1:
            wanted: list[StorySpec] = json.loads(Path(sys.argv[1]).read_text())
        else:
            wanted = demo_stories(session)
        for story in wanted:
            try:
                saved = stories.save_story(
                    session,
                    story["slug"],
                    story["name"],
                    story["blurb"],
                    story["urls"],
                )
            except stories.StoryError as exc:
                session.rollback()
                logger.warning("Skipped %s: %s", story["slug"], exc)
                continue
            logger.info("Saved %s", saved)


if __name__ == "__main__":
    main()
