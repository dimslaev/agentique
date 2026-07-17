"""Load the controlled tag vocabulary into the `tag` table.

Unlike `seed_articles`, this is real data, not sample data: `pipeline.tags.
load_vocabulary()` raises on an empty `tag` table, so every environment —
production included — needs it. Idempotent, keyed on `slug`; tags no longer in
the file are left alone, because `article_tag` rows may still point at them.
"""

import json
from pathlib import Path

from sqlmodel import Session, select

from app.core.db import engine
from app.models import Tag

TAGS_FILE = Path(__file__).parent / "data" / "tags.json"


def load_tags() -> list[dict[str, str]]:
    with TAGS_FILE.open() as f:
        return json.load(f)["tags"]


def seed(session: Session) -> None:
    existing = {t.slug: t for t in session.exec(select(Tag)).all()}
    for entry in load_tags():
        tag = existing.get(entry["slug"])
        if tag is None:
            session.add(
                Tag(
                    slug=entry["slug"],
                    name=entry["name"],
                    description=entry.get("description"),
                )
            )
        else:
            tag.name = entry["name"]
            tag.description = entry.get("description")
            session.add(tag)
    session.commit()


def main() -> None:
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    main()
