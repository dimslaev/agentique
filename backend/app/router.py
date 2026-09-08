"""Aggregates every domain router into the versioned API router mounted by app.main."""

from __future__ import annotations

from fastapi import APIRouter

from app.analytics.routes import router as analytics_router
from app.audience.routes import likes_router, login_router, users_router
from app.catalog.routes import router as catalog_router

# Registration order is the order the endpoints appear in the OpenAPI document,
# and the generated client follows that document. Reordering churns the client
# for no behaviour change.
api_router = APIRouter()
api_router.include_router(login_router)
api_router.include_router(users_router)
api_router.include_router(catalog_router)
api_router.include_router(likes_router)
api_router.include_router(analytics_router)
