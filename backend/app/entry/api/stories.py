"""The right rail's stories, for the public feed."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.entry.api.deps import SessionDep
from app.features.stories import service
from app.features.stories.model import StoryPublic

router = APIRouter(prefix="/stories", tags=["stories"])


@router.get("/", response_model=list[StoryPublic])
def read_stories(
    session: SessionDep, limit: int = Query(default=5, ge=1, le=20)
) -> list[StoryPublic]:
    return service.list_stories(session, limit)
