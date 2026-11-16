"""
SysForge — Health check route.

Exposed at:
  GET /api/v1/health   (versioned — primary contract)
  GET /health          (bare — infrastructure / load-balancer probes)

Both paths serve the same handler; the bare path is mounted without the
version prefix in ``main.py`` and is hidden from the OpenAPI schema.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.models.responses import HealthResponse
from app.services.analysis_service import session_count

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Returns the service status, name, and version.  "
        "An HTTP 200 with ``status: ok`` confirms the backend is running."
    ),
)
async def health_check() -> HealthResponse:
    """
    Return service health status.

    This endpoint is intentionally lightweight — it should never perform
    database queries or heavy computation.
    """
    return HealthResponse(
        status="ok",
        service="sysforge-backend",
        version=settings.app_version,
    )
