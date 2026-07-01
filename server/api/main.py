"""
api.main - FastAPI application factory and router wiring.

Run with:  uvicorn api.main:app --reload

SEAMLESS-MERGE DESIGN
---------------------
Router registration is DIRECTORY-DRIVEN, not an allowlist. Drop ANY file into
`api/routes/<anything>.py` exposing a module-level `router` (and/or
`internal_router`, a FastAPI APIRouter) and it auto-mounts under `/api/v1` - no
edits to this file, no merge conflict here, regardless of the filename M2/M3/M4
choose (intake.py, blast.py, dashboard.py, ws.py, …). So:

  • the app boots today with ONLY Member 1's code present, and
  • the moment a teammate merges a route file, it mounts on next start.

A file that is present but fails to import is logged LOUDLY (it's a real bug in
that router) instead of being silently skipped as if absent.

All routers mount under the shared `/api/v1` prefix (SoW §12.1).
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

import api.routes as routes_pkg
from core.logging_utils import get_logger
from core.responses import ok, register_exception_handlers
from services.neo4j_client import neo4j_client

log = get_logger(__name__)

API_PREFIX = "/api/v1"

# Router attribute names a route module may expose. `internal_router` carries the
# X-Internal-Key-guarded routes (e.g. /internal/validate).
_ROUTER_ATTRS = ("router", "internal_router")


def _register_routers(app: FastAPI) -> None:
    """Discover and mount every router under api/routes/ (directory-driven)."""
    # Sort so 'match' (Member 1) mounts first for stable, predictable ordering;
    # FastAPI route resolution is otherwise order-independent across files here.
    module_names = sorted(
        name for _, name, ispkg in pkgutil.iter_modules(routes_pkg.__path__) if not ispkg
    )
    for name in module_names:
        module_path = f"{routes_pkg.__name__}.{name}"
        try:
            module = importlib.import_module(module_path)
        except Exception as exc:  # present but broken - surface it, don't hide it
            log.error("FAILED to import router %s: %s", module_path, exc)
            continue

        mounted_any = False
        for attr in _ROUTER_ATTRS:
            router = getattr(module, attr, None)
            if isinstance(router, APIRouter):
                app.include_router(router, prefix=API_PREFIX)
                log.info("mounted %s.%s", module_path, attr)
                mounted_any = True
        if not mounted_any:
            log.warning("%s exposes no `router`/`internal_router` - skipped", module_path)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Connect shared clients on startup; close them on shutdown."""
    await neo4j_client.connect()  # logs + degrades gracefully if Neo4j is down
    log.info("NANDI API up")
    try:
        yield
    finally:
        await neo4j_client.close()
        log.info("NANDI API down")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="NANDI API",
        version="2.0.0",
        description="Missing Persons Reunification System - Kumbh Mela 2027",
        lifespan=lifespan,
    )

    # CORS is permissive for the hackathon; M4 can tighten origins for prod.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    _register_routers(app)

    from fastapi.staticfiles import StaticFiles
    import os
    os.makedirs("uploads", exist_ok=True)
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        """Liveness probe - returns the standard envelope."""
        return ok({"status": "ok", "service": "nandi-api"})

    return app


# Uvicorn entrypoint.
app = create_app()
