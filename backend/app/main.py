"""FastAPI application entry point: wires the API routers, the MCP app, CORS, and the health check."""

from __future__ import annotations

import sentry_sdk
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.entry.api import analytics, articles, likes, login, stories, users
from app.entry.mcp.server import mcp_app


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "development":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    # The MCP app's session manager starts here: a mounted ASGI app never runs
    # its own lifespan.
    lifespan=mcp_app.lifespan,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Registration order is the order the endpoints appear in the OpenAPI document,
# and the generated client follows that document. Reordering churns the client
# for no behaviour change.
api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(articles.router)
api_router.include_router(likes.router)
api_router.include_router(analytics.router)
api_router.include_router(stories.router)
app.include_router(api_router, prefix=settings.API_V1_STR)
# Outside the versioned API on purpose: it is an MCP endpoint, not a REST
# resource, and it carries its own bearer-token auth rather than a user JWT.
app.mount("/mcp", mcp_app)


@app.get(f"{settings.API_V1_STR}/utils/health-check/", tags=["utils"])
async def health_check() -> bool:
    return True
