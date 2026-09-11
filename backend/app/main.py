"""FastAPI application entry point: wires routers, CORS, and the health check."""

from __future__ import annotations

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.mcp.server import mcp_app
from app.newsletter.routes import router as newsletter_router
from app.platform.settings import settings
from app.router import api_router


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
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

app.include_router(api_router, prefix=settings.API_V1_STR)
# The newsletter lives outside /api/v1 because the public signup form has
# posted to /api/newsletter/subscribe since before the API was versioned.
app.include_router(newsletter_router, prefix="/api")
# Outside the versioned API on purpose: it is an MCP endpoint, not a REST
# resource, and it carries its own bearer-token auth rather than a user JWT.
app.mount("/mcp", mcp_app)


@app.get(f"{settings.API_V1_STR}/utils/health-check/", tags=["utils"])
async def health_check() -> bool:
    return True
