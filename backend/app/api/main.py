"""Aggregates every domain router into the versioned API router mounted by app.main."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    analytics,
    articles,
    likes,
    login,
    users,
)

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(articles.router)
api_router.include_router(likes.router)
api_router.include_router(analytics.router)
