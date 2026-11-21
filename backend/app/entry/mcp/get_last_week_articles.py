"""The `get_last_week_articles` tool: the week's published articles and what readers liked."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field
from sqlmodel import Session

from app.core.db.engine import engine
from app.features.newsletter import service as newsletter
from app.features.newsletter.model import Week


def get_last_week_articles(days: Annotated[int, Field(ge=1, le=30)] = 7) -> Week:
    """The weekly newsletter's material.

    `articles`: every article published in the last `days`, the most liked
    first, then the highest score. Each has `url`, `title`, `publisher`,
    `publisher_kind` (`lab`, `company`, `individual`, `media`, `community`,
    `unknown`), `kind`, `score`, `likes`, and the `summary` curation wrote
    after reading it.

    `liked`: articles readers liked in the last `days`, however old, most
    likes in the window first. Same fields, plus `published_at`.
    """
    with Session(engine) as session:
        return {
            "articles": newsletter.get_last_week_articles(session, days),
            "liked": newsletter.liked(session, days),
        }
