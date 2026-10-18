"""FastAPI application factory and ASGI entrypoint.

Run locally with:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.session import init_db
from app.services.file_service import FileNotFound, UnsupportedFileType

import logging

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks.

    Startup creates the SQLite tables (dev convenience) and makes sure the
    upload & ChromaDB directories exist. Replace `init_db()` with Alembic
    `upgrade head` once migrations are seeded in production.
    """

    from pathlib import Path

    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.chroma_persist_directory).mkdir(parents=True, exist_ok=True)

    init_db()

    # Keep the RAG index in sync with published files. The embedding backend
    # is optional (offline dev machines without a key must still boot), so
    # failures here are logged, never fatal.
    try:
        from app.services.vector_store import ensure_published_indexed

        index_summary = ensure_published_indexed()
        if index_summary.get("indexed_files"):
            logger.info("Startup RAG sweep: %s", index_summary)
        elif index_summary.get("skipped"):
            logger.info("Startup RAG sweep skipped: %s", index_summary["skipped"])
    except Exception as exc:  # noqa: BLE001 - optional subsystem
        logger.warning("Startup RAG sweep failed: %s", exc)

    yield

    # Nothing to tear down: the engine's pool is closed on process exit.


def create_app() -> FastAPI:
    """Build the ASGI application."""

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Data Mining Academy — educational platform for learning Data Mining "
            "in Arabic with English terminology."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — lets the Vite dev server (port 5173) call the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Domain exceptions -> proper HTTP status codes.
    # Registered before the catch-all so it wins the dispatch.
    @app.exception_handler(FileNotFound)
    async def file_not_found_handler(request: Request, exc: FileNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(UnsupportedFileType)
    async def unsupported_type_handler(
        request: Request, exc: UnsupportedFileType
    ) -> JSONResponse:
        return JSONResponse(status_code=415, content={"detail": str(exc)})

    # Global fallback: never leak a raw 500 stack trace to the client.
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "path": request.url.path},
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
        }

    return app


app = create_app()
