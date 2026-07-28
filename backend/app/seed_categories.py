"""Load the controlled category vocabulary into the `category` table.

Real data, not sample data: `pipeline.categories.load_vocabulary()` raises on an
empty table, so every environment — production included — needs it. Idempotent,
keyed on `slug`; categories no longer in the file are deactivated rather than
deleted, because `article_category` rows still point at them.

Editing `data/categories.json` and re-running this is how a category definition
changes. That changes what gets ingested *going forward* — the back catalogue
was filtered under the old definitions.
"""

import json
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.db import engine
from app.models import Category

CATEGORIES_FILE = Path(__file__).parent / "data" / "categories.json"


def load_categories() -> list[dict[str, Any]]:
    with CATEGORIES_FILE.open() as f:
        return json.load(f)["categories"]


def seed(session: Session) -> None:
    entries = load_categories()
    existing = {c.slug: c for c in session.exec(select(Category)).all()}

    for entry in entries:
        category = existing.get(entry["slug"])
        if category is None:
            category = Category(slug=entry["slug"])
        category.name = entry["name"]
        category.description = entry["description"]
        category.exemplars = entry.get("exemplars", [])
        category.position = entry.get("position", 0)
        category.is_active = True
        session.add(category)

    # A category dropped from the file stops matching new articles but keeps its
    # rows, so old articles do not lose their only category.
    seeded = {e["slug"] for e in entries}
    for slug, category in existing.items():
        if slug not in seeded and category.is_active:
            category.is_active = False
            session.add(category)

    session.commit()


def main() -> None:
    with Session(engine) as session:
        seed(session)


if __name__ == "__main__":
    main()
