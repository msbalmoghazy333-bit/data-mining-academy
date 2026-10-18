"""Health-check endpoint — verifies the API and the database are alive."""

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check")
def get_health() -> dict:
    """Lightweight probe used by load balancers, Docker and the front-end."""

    settings = get_settings()

    # Round-trip a trivial query so a broken DB is reported as `degraded`.
    database_ok = True
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - defensive
        database_ok = False

    return {
        "status": "ok" if database_ok else "degraded",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "database": "connected" if database_ok else "unreachable",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
